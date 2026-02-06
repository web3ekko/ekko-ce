use std::collections::HashSet;
use std::io::Cursor;
use std::time::Instant;

use alert_runtime_common::{
    polars_eval_response_schema_version_v1, AlertExecutableV1, AlertTemplateV1, AlertVariableV1,
    ConditionSetV1, DatasourceRefV1, EnrichmentV1, ExprOpV1, ExprOperandV1, ExprV1, OutputFieldV1,
    PolarsEvalErrorV1, PolarsEvalMatchV1, PolarsEvalRequestV1, PolarsEvalRequestV2,
    PolarsEvalResponseV1, PolarsEvalTimingsV1,
};
use base64::engine::general_purpose::STANDARD as BASE64;
use base64::Engine as _;
use polars::prelude::*;
use polars_io::ipc::IpcStreamReader;
use serde_json::Value;

#[derive(Debug, Clone)]
pub struct EvalLimits {
    pub max_decoded_frame_bytes: usize,
    pub max_rows: usize,
    pub max_columns: usize,
    pub max_datasources: usize,
    pub max_enrichments: usize,
    pub max_condition_nodes: usize,
    pub max_expression_depth: usize,
    pub max_output_fields: usize,
}

impl Default for EvalLimits {
    fn default() -> Self {
        Self {
            max_decoded_frame_bytes: 25 * 1024 * 1024,
            max_rows: 10_000,
            max_columns: 256,
            max_datasources: 32,
            max_enrichments: 64,
            max_condition_nodes: 256,
            max_expression_depth: 32,
            max_output_fields: 64,
        }
    }
}

#[derive(Debug, thiserror::Error)]
pub enum EvalFailure {
    #[error("invalid_template: {0}")]
    InvalidTemplate(String),
    #[error("schema_mismatch: {0}")]
    SchemaMismatch(String),
    #[error("eval_error: {0}")]
    EvalError(String),
    #[error("payload_too_large: {0}")]
    PayloadTooLarge(String),
}

impl EvalFailure {
    fn to_wire_error(&self) -> PolarsEvalErrorV1 {
        match self {
            Self::InvalidTemplate(message) => PolarsEvalErrorV1 {
                code: "invalid_template".to_string(),
                message: message.clone(),
            },
            Self::SchemaMismatch(message) => PolarsEvalErrorV1 {
                code: "schema_mismatch".to_string(),
                message: message.clone(),
            },
            Self::EvalError(message) => PolarsEvalErrorV1 {
                code: "eval_error".to_string(),
                message: message.clone(),
            },
            Self::PayloadTooLarge(message) => PolarsEvalErrorV1 {
                code: "payload_too_large".to_string(),
                message: message.clone(),
            },
        }
    }
}

trait EvalRequestLike {
    fn request_id(&self) -> &str;
    fn job_id(&self) -> &str;
    fn run_id(&self) -> &str;
    fn evaluation_context(&self) -> &alert_runtime_common::EvaluationContextV1;
    fn frame(&self) -> &alert_runtime_common::ArrowFrameV1;
    fn output_fields(&self) -> &[OutputFieldV1];
}

impl EvalRequestLike for PolarsEvalRequestV1 {
    fn request_id(&self) -> &str {
        self.request_id.as_str()
    }
    fn job_id(&self) -> &str {
        self.job_id.as_str()
    }
    fn run_id(&self) -> &str {
        self.run_id.as_str()
    }
    fn evaluation_context(&self) -> &alert_runtime_common::EvaluationContextV1 {
        &self.evaluation_context
    }
    fn frame(&self) -> &alert_runtime_common::ArrowFrameV1 {
        &self.frame
    }
    fn output_fields(&self) -> &[OutputFieldV1] {
        self.output_fields.as_slice()
    }
}

impl EvalRequestLike for PolarsEvalRequestV2 {
    fn request_id(&self) -> &str {
        self.request_id.as_str()
    }
    fn job_id(&self) -> &str {
        self.job_id.as_str()
    }
    fn run_id(&self) -> &str {
        self.run_id.as_str()
    }
    fn evaluation_context(&self) -> &alert_runtime_common::EvaluationContextV1 {
        &self.evaluation_context
    }
    fn frame(&self) -> &alert_runtime_common::ArrowFrameV1 {
        &self.frame
    }
    fn output_fields(&self) -> &[OutputFieldV1] {
        self.output_fields.as_slice()
    }
}

trait EvalSpecLike {
    fn datasources(&self) -> &[DatasourceRefV1];
    fn enrichments(&self) -> &[EnrichmentV1];
    fn conditions(&self) -> &ConditionSetV1;
    fn variables(&self) -> &[AlertVariableV1];
}

impl EvalSpecLike for AlertTemplateV1 {
    fn datasources(&self) -> &[DatasourceRefV1] {
        self.datasources.as_slice()
    }
    fn enrichments(&self) -> &[EnrichmentV1] {
        self.enrichments.as_slice()
    }
    fn conditions(&self) -> &ConditionSetV1 {
        &self.conditions
    }
    fn variables(&self) -> &[AlertVariableV1] {
        self.variables.as_slice()
    }
}

impl EvalSpecLike for AlertExecutableV1 {
    fn datasources(&self) -> &[DatasourceRefV1] {
        self.datasources.as_slice()
    }
    fn enrichments(&self) -> &[EnrichmentV1] {
        self.enrichments.as_slice()
    }
    fn conditions(&self) -> &ConditionSetV1 {
        &self.conditions
    }
    fn variables(&self) -> &[AlertVariableV1] {
        self.variables.as_slice()
    }
}

pub fn evaluate_request(req: &PolarsEvalRequestV1, limits: &EvalLimits) -> PolarsEvalResponseV1 {
    evaluate_spec(req, &req.template, limits)
}

pub fn evaluate_request_v2(req: &PolarsEvalRequestV2, limits: &EvalLimits) -> PolarsEvalResponseV1 {
    evaluate_spec(req, &req.executable, limits)
}

fn evaluate_spec(
    req: &impl EvalRequestLike,
    spec: &impl EvalSpecLike,
    limits: &EvalLimits,
) -> PolarsEvalResponseV1 {
    let total_start = Instant::now();

    let instance_id = req.evaluation_context().instance.instance_id.clone();
    let partition = req.evaluation_context().partition.clone();

    let mut rows_evaluated: i64 = 0;
    let mut timings = PolarsEvalTimingsV1 {
        total: 0,
        enrichments: 0,
        conditions: 0,
    };

    let result = (|| -> Result<Vec<PolarsEvalMatchV1>, EvalFailure> {
        let df = decode_frame(req, limits)?;
        rows_evaluated = df.height() as i64;

        validate_request_invariants(req, &df, limits)?;
        validate_spec(spec, req, limits)?;

        let enrich_start = Instant::now();
        let df_enriched = apply_enrichments(spec, req, df)?;
        timings.enrichments = enrich_start.elapsed().as_millis() as u64;

        let cond_start = Instant::now();
        let matched_df = apply_conditions_and_select(spec, req, df_enriched)?;
        timings.conditions = cond_start.elapsed().as_millis() as u64;

        Ok(build_matches(req, matched_df)?)
    })();

    timings.total = total_start.elapsed().as_millis() as u64;

    match result {
        Ok(matched) => PolarsEvalResponseV1 {
            schema_version: polars_eval_response_schema_version_v1(),
            request_id: req.request_id().to_string(),
            job_id: req.job_id().to_string(),
            run_id: req.run_id().to_string(),
            instance_id,
            partition,
            rows_evaluated,
            matched,
            error: None,
            timings_ms: Some(timings),
        },
        Err(err) => PolarsEvalResponseV1 {
            schema_version: polars_eval_response_schema_version_v1(),
            request_id: req.request_id().to_string(),
            job_id: req.job_id().to_string(),
            run_id: req.run_id().to_string(),
            instance_id,
            partition,
            rows_evaluated,
            matched: Vec::new(),
            error: Some(err.to_wire_error()),
            timings_ms: Some(timings),
        },
    }
}

fn decode_frame(req: &impl EvalRequestLike, limits: &EvalLimits) -> Result<DataFrame, EvalFailure> {
    if req.frame().format != "arrow_ipc_stream_base64" {
        return Err(EvalFailure::EvalError(format!(
            "unsupported frame.format '{}'",
            req.frame().format
        )));
    }

    let decoded = BASE64
        .decode(req.frame().data.as_bytes())
        .map_err(|e| EvalFailure::EvalError(format!("base64 decode failed: {e}")))?;

    if decoded.len() > limits.max_decoded_frame_bytes {
        return Err(EvalFailure::PayloadTooLarge(format!(
            "decoded frame is {} bytes (max {})",
            decoded.len(),
            limits.max_decoded_frame_bytes
        )));
    }

    let cursor = Cursor::new(decoded);
    IpcStreamReader::new(cursor)
        .finish()
        .map_err(|e| EvalFailure::EvalError(format!("failed to decode ipc stream: {e}")))
}

fn validate_request_invariants(
    req: &impl EvalRequestLike,
    df: &DataFrame,
    limits: &EvalLimits,
) -> Result<(), EvalFailure> {
    if df.height() > limits.max_rows {
        return Err(EvalFailure::PayloadTooLarge(format!(
            "frame has {} rows (max {})",
            df.height(),
            limits.max_rows
        )));
    }
    if df.width() > limits.max_columns {
        return Err(EvalFailure::PayloadTooLarge(format!(
            "frame has {} columns (max {})",
            df.width(),
            limits.max_columns
        )));
    }

    if !df
        .get_column_names()
        .iter()
        .any(|name| *name == "target_key")
    {
        return Err(EvalFailure::SchemaMismatch(
            "frame missing required column 'target_key'".to_string(),
        ));
    }

    let expected = &req.evaluation_context().targets.keys;
    if df.height() != expected.len() {
        return Err(EvalFailure::SchemaMismatch(format!(
            "frame rows ({}) must equal evaluation_context.targets.keys ({})",
            df.height(),
            expected.len()
        )));
    }

    let col = df
        .column("target_key")
        .map_err(|e| EvalFailure::SchemaMismatch(format!("failed to read target_key: {e}")))?;
    let utf8 = col
        .str()
        .map_err(|e| EvalFailure::SchemaMismatch(format!("target_key must be string: {e}")))?;

    for (idx, expected_key) in expected.iter().enumerate() {
        let got = utf8.get(idx).ok_or_else(|| {
            EvalFailure::SchemaMismatch(format!("target_key row {} is null", idx))
        })?;
        if got != expected_key {
            return Err(EvalFailure::SchemaMismatch(format!(
                "target_key row {} mismatch (got '{}', expected '{}')",
                idx, got, expected_key
            )));
        }
    }

    Ok(())
}

fn validate_spec(
    spec: &impl EvalSpecLike,
    req: &impl EvalRequestLike,
    limits: &EvalLimits,
) -> Result<(), EvalFailure> {
    if spec.datasources().len() > limits.max_datasources {
        return Err(EvalFailure::InvalidTemplate(format!(
            "template has {} datasources (max {})",
            spec.datasources().len(),
            limits.max_datasources
        )));
    }
    if spec.enrichments().len() > limits.max_enrichments {
        return Err(EvalFailure::InvalidTemplate(format!(
            "template has {} enrichments (max {})",
            spec.enrichments().len(),
            limits.max_enrichments
        )));
    }
    if req.output_fields().len() > limits.max_output_fields {
        return Err(EvalFailure::InvalidTemplate(format!(
            "request has {} output_fields (max {})",
            req.output_fields().len(),
            limits.max_output_fields
        )));
    }

    let mut nodes = 0usize;
    for enrich in spec.enrichments().iter() {
        count_expr_nodes(&enrich.expr, 1, limits, &mut nodes)?;
    }
    for expr in spec.conditions().all.iter() {
        count_expr_nodes(expr, 1, limits, &mut nodes)?;
    }
    for expr in spec.conditions().any.iter() {
        count_expr_nodes(expr, 1, limits, &mut nodes)?;
    }
    for expr in spec.conditions().not.iter() {
        count_expr_nodes(expr, 1, limits, &mut nodes)?;
    }

    Ok(())
}

fn count_expr_nodes(
    expr: &ExprV1,
    depth: usize,
    limits: &EvalLimits,
    nodes: &mut usize,
) -> Result<(), EvalFailure> {
    *nodes += 1;
    if *nodes > limits.max_condition_nodes {
        return Err(EvalFailure::InvalidTemplate(format!(
            "expression node count exceeded max {}",
            limits.max_condition_nodes
        )));
    }
    if depth > limits.max_expression_depth {
        return Err(EvalFailure::InvalidTemplate(format!(
            "expression depth exceeded max {}",
            limits.max_expression_depth
        )));
    }
    if let Some(left) = expr.left.as_ref() {
        count_operand_nodes(left, depth + 1, limits, nodes)?;
    }
    if let Some(right) = expr.right.as_ref() {
        count_operand_nodes(right, depth + 1, limits, nodes)?;
    }
    if let Some(values) = expr.values.as_ref() {
        for v in values {
            count_operand_nodes(v, depth + 1, limits, nodes)?;
        }
    }
    Ok(())
}

fn count_operand_nodes(
    op: &ExprOperandV1,
    depth: usize,
    limits: &EvalLimits,
    nodes: &mut usize,
) -> Result<(), EvalFailure> {
    match op {
        ExprOperandV1::Expr(inner) => count_expr_nodes(inner, depth, limits, nodes),
        ExprOperandV1::Literal(_) => Ok(()),
    }
}

fn apply_enrichments(
    spec: &impl EvalSpecLike,
    req: &impl EvalRequestLike,
    df: DataFrame,
) -> Result<DataFrame, EvalFailure> {
    let mut available_columns: HashSet<String> = df
        .get_column_names()
        .iter()
        .map(|s| (*s).to_string())
        .collect();

    let mut lf = df.lazy();
    for enrich in spec.enrichments().iter() {
        let out_col = enrichment_output_column(&enrich.output)?;
        let expr = compile_expr(&enrich.expr, req, &available_columns, true)?;
        lf = lf.with_columns([expr.alias(out_col.as_str())]);
        available_columns.insert(out_col);
    }

    lf.collect()
        .map_err(|e| EvalFailure::EvalError(format!("failed to compute enrichments: {e}")))
}

fn apply_conditions_and_select(
    spec: &impl EvalSpecLike,
    req: &impl EvalRequestLike,
    df: DataFrame,
) -> Result<DataFrame, EvalFailure> {
    let available_columns: HashSet<String> = df
        .get_column_names()
        .iter()
        .map(|s| (*s).to_string())
        .collect();

    let cond = compile_condition_set(spec.conditions(), req, &available_columns)?;
    let cond = cond.fill_null(lit(false));

    let mut selections: Vec<Expr> = Vec::with_capacity(1 + req.output_fields().len());
    selections.push(col("target_key"));
    for field in req.output_fields().iter() {
        let (col_name, alias) = output_field_column(field)?;
        if !available_columns.contains(&col_name) {
            return Err(EvalFailure::SchemaMismatch(format!(
                "missing required output field column '{}'",
                col_name
            )));
        }
        selections.push(col(&col_name).alias(&alias));
    }

    df.lazy()
        .filter(cond)
        .select(selections)
        .collect()
        .map_err(|e| EvalFailure::EvalError(format!("failed to evaluate conditions: {e}")))
}

fn build_matches(
    req: &impl EvalRequestLike,
    df: DataFrame,
) -> Result<Vec<PolarsEvalMatchV1>, EvalFailure> {
    let target = df
        .column("target_key")
        .map_err(|e| EvalFailure::SchemaMismatch(format!("missing target_key: {e}")))?
        .str()
        .map_err(|e| EvalFailure::SchemaMismatch(format!("target_key must be string: {e}")))?;

    let mut matched = Vec::with_capacity(df.height());
    for row_idx in 0..df.height() {
        let Some(target_key) = target.get(row_idx) else {
            continue;
        };

        let mut ctx = serde_json::Map::new();
        for field in req.output_fields().iter() {
            let (_, alias) = output_field_column(field)?;
            let s = df.column(&alias).map_err(|e| {
                EvalFailure::SchemaMismatch(format!("missing output column '{}': {e}", alias))
            })?;
            let v = s
                .get(row_idx)
                .map_err(|e| EvalFailure::EvalError(format!("failed reading '{}': {e}", alias)))?;
            ctx.insert(alias, anyvalue_to_json(v));
        }

        matched.push(PolarsEvalMatchV1 {
            target_key: target_key.to_string(),
            match_context: Value::Object(ctx),
        });
    }

    Ok(matched)
}

fn compile_condition_set(
    conditions: &ConditionSetV1,
    req: &impl EvalRequestLike,
    available_columns: &HashSet<String>,
) -> Result<Expr, EvalFailure> {
    let all_expr = reduce_bool_and(
        conditions
            .all
            .iter()
            .map(|e| compile_expr(e, req, available_columns, false))
            .collect::<Result<Vec<_>, _>>()?,
    );

    let any_expr = if conditions.any.is_empty() {
        lit(true)
    } else {
        reduce_bool_or(
            conditions
                .any
                .iter()
                .map(|e| compile_expr(e, req, available_columns, false))
                .collect::<Result<Vec<_>, _>>()?,
        )
    };

    let not_expr = if conditions.not.is_empty() {
        lit(true)
    } else {
        let disallowed = reduce_bool_or(
            conditions
                .not
                .iter()
                .map(|e| compile_expr(e, req, available_columns, false))
                .collect::<Result<Vec<_>, _>>()?,
        );
        disallowed.not()
    };

    Ok(all_expr.and(any_expr).and(not_expr))
}

fn reduce_bool_and(exprs: Vec<Expr>) -> Expr {
    exprs.into_iter().fold(lit(true), |acc, e| acc.and(e))
}

fn reduce_bool_or(mut exprs: Vec<Expr>) -> Expr {
    let Some(first) = exprs.pop() else {
        return lit(false);
    };
    exprs.into_iter().fold(first, |acc, e| acc.or(e))
}

fn compile_expr(
    expr: &ExprV1,
    req: &impl EvalRequestLike,
    available_columns: &HashSet<String>,
    enrichment_phase: bool,
) -> Result<Expr, EvalFailure> {
    let left = expr
        .left
        .as_ref()
        .map(|o| compile_operand(o, req, available_columns, enrichment_phase))
        .transpose()?;
    let right = expr
        .right
        .as_ref()
        .map(|o| compile_operand(o, req, available_columns, enrichment_phase))
        .transpose()?;

    match expr.op {
        ExprOpV1::Add => Ok(left.ok_or_else(|| missing_operand("left"))?
            + right.ok_or_else(|| missing_operand("right"))?),
        ExprOpV1::Sub => Ok(left.ok_or_else(|| missing_operand("left"))?
            - right.ok_or_else(|| missing_operand("right"))?),
        ExprOpV1::Mul => Ok(left.ok_or_else(|| missing_operand("left"))?
            * right.ok_or_else(|| missing_operand("right"))?),
        ExprOpV1::Div => Ok(left.ok_or_else(|| missing_operand("left"))?
            / right.ok_or_else(|| missing_operand("right"))?),
        ExprOpV1::Gt => Ok(left
            .ok_or_else(|| missing_operand("left"))?
            .gt(right.ok_or_else(|| missing_operand("right"))?)),
        ExprOpV1::Gte => Ok(left
            .ok_or_else(|| missing_operand("left"))?
            .gt_eq(right.ok_or_else(|| missing_operand("right"))?)),
        ExprOpV1::Lt => Ok(left
            .ok_or_else(|| missing_operand("left"))?
            .lt(right.ok_or_else(|| missing_operand("right"))?)),
        ExprOpV1::Lte => Ok(left
            .ok_or_else(|| missing_operand("left"))?
            .lt_eq(right.ok_or_else(|| missing_operand("right"))?)),
        ExprOpV1::Eq => Ok(left
            .ok_or_else(|| missing_operand("left"))?
            .eq(right.ok_or_else(|| missing_operand("right"))?)),
        ExprOpV1::Neq => Ok(left
            .ok_or_else(|| missing_operand("left"))?
            .neq(right.ok_or_else(|| missing_operand("right"))?)),
        ExprOpV1::And => Ok(left
            .ok_or_else(|| missing_operand("left"))?
            .and(right.ok_or_else(|| missing_operand("right"))?)),
        ExprOpV1::Or => Ok(left
            .ok_or_else(|| missing_operand("left"))?
            .or(right.ok_or_else(|| missing_operand("right"))?)),
        ExprOpV1::Not => {
            if let Some(left) = left {
                Ok(left.not())
            } else if let Some(values) = expr.values.as_ref() {
                let first = values.first().ok_or_else(|| {
                    EvalFailure::InvalidTemplate("not requires an operand".to_string())
                })?;
                Ok(compile_operand(first, req, available_columns, enrichment_phase)?.not())
            } else {
                Err(EvalFailure::InvalidTemplate(
                    "not requires an operand".to_string(),
                ))
            }
        }
        ExprOpV1::Coalesce => {
            let mut items: Vec<Expr> = Vec::new();
            if let Some(values) = expr.values.as_ref() {
                for v in values {
                    items.push(compile_operand(
                        v,
                        req,
                        available_columns,
                        enrichment_phase,
                    )?);
                }
            } else {
                if let Some(left) = left {
                    items.push(left);
                }
                if let Some(right) = right {
                    items.push(right);
                }
            }

            if items.is_empty() {
                return Err(EvalFailure::InvalidTemplate(
                    "coalesce requires operands".to_string(),
                ));
            }

            Ok(coalesce(&items))
        }
    }
}

fn missing_operand(which: &str) -> EvalFailure {
    EvalFailure::InvalidTemplate(format!("missing operand '{}'", which))
}

fn compile_operand(
    operand: &ExprOperandV1,
    req: &impl EvalRequestLike,
    available_columns: &HashSet<String>,
    enrichment_phase: bool,
) -> Result<Expr, EvalFailure> {
    match operand {
        ExprOperandV1::Expr(inner) => compile_expr(inner, req, available_columns, enrichment_phase),
        ExprOperandV1::Literal(lit_val) => {
            literal_to_expr(lit_val, req, available_columns, enrichment_phase)
        }
    }
}

fn literal_to_expr(
    value: &Value,
    req: &impl EvalRequestLike,
    available_columns: &HashSet<String>,
    enrichment_phase: bool,
) -> Result<Expr, EvalFailure> {
    match value {
        Value::String(s) => {
            let s = s.trim();
            if let Some(path) = s.strip_prefix("$.") {
                let col_name = ref_to_column_name(path)?;

                if col_name.starts_with("enrichment__")
                    && enrichment_phase
                    && !available_columns.contains(&col_name)
                {
                    return Err(EvalFailure::InvalidTemplate(format!(
                        "enrichment reference '{}' used before it is computed",
                        s
                    )));
                }
                if !col_name.starts_with("enrichment__") && !available_columns.contains(&col_name) {
                    return Err(EvalFailure::SchemaMismatch(format!(
                        "frame missing required column '{}'",
                        col_name
                    )));
                }
                return Ok(col(&col_name));
            }

            if let Some(var_name) = parse_variable_placeholder(s) {
                let v = resolve_variable(req, &var_name)?;
                return literal_to_expr(&v, req, available_columns, enrichment_phase);
            }

            Ok(lit(s.to_string()))
        }
        Value::Number(n) => {
            if let Some(i) = n.as_i64() {
                Ok(lit(i))
            } else if let Some(f) = n.as_f64() {
                Ok(lit(f))
            } else {
                Err(EvalFailure::InvalidTemplate(format!(
                    "invalid number literal {}",
                    n
                )))
            }
        }
        Value::Bool(b) => Ok(lit(*b)),
        Value::Null => Ok(lit(Null {})),
        other => Err(EvalFailure::InvalidTemplate(format!(
            "unsupported literal value {}",
            other
        ))),
    }
}

fn resolve_variable(req: &impl EvalRequestLike, name: &str) -> Result<Value, EvalFailure> {
    let vars = req
        .evaluation_context()
        .variables
        .as_object()
        .ok_or_else(|| {
            EvalFailure::InvalidTemplate(
                "evaluation_context.variables must be an object".to_string(),
            )
        })?;
    vars.get(name)
        .cloned()
        .ok_or_else(|| EvalFailure::InvalidTemplate(format!("variable '{}' not found", name)))
}

fn parse_variable_placeholder(text: &str) -> Option<String> {
    let inner = text.strip_prefix("{{")?.strip_suffix("}}")?;
    let name = inner.trim();
    if name.is_empty() {
        return None;
    }
    Some(name.to_string())
}

fn ref_to_column_name(path_without_dollar: &str) -> Result<String, EvalFailure> {
    if let Some(rest) = path_without_dollar.strip_prefix("datasources.") {
        let mut parts = rest.splitn(2, '.');
        let ds_id = parts.next().unwrap_or_default();
        let col = parts.next().unwrap_or_default();
        if ds_id.is_empty() || col.is_empty() {
            return Err(EvalFailure::InvalidTemplate(format!(
                "invalid datasource ref '$.{path_without_dollar}'"
            )));
        }
        return Ok(format!("{ds_id}__{col}"));
    }

    if let Some(rest) = path_without_dollar.strip_prefix("enrichment.") {
        let name = rest.trim();
        if name.is_empty() {
            return Err(EvalFailure::InvalidTemplate(format!(
                "invalid enrichment ref '$.{path_without_dollar}'"
            )));
        }
        return Ok(format!("enrichment__{name}"));
    }

    if let Some(rest) = path_without_dollar.strip_prefix("tx.") {
        let field = rest.trim();
        if field.is_empty() {
            return Err(EvalFailure::InvalidTemplate(format!(
                "invalid tx ref '$.{path_without_dollar}'"
            )));
        }
        return Ok(format!("tx__{field}"));
    }

    Err(EvalFailure::InvalidTemplate(format!(
        "unsupported ref '$.{path_without_dollar}'"
    )))
}

fn enrichment_output_column(output: &str) -> Result<String, EvalFailure> {
    let output = output.trim();
    let Some(path) = output.strip_prefix("$.enrichment.") else {
        return Err(EvalFailure::InvalidTemplate(format!(
            "enrichment.output must start with '$.enrichment.' (got '{}')",
            output
        )));
    };
    if path.is_empty() {
        return Err(EvalFailure::InvalidTemplate(
            "enrichment.output missing name".to_string(),
        ));
    }
    Ok(format!("enrichment__{}", path))
}

fn output_field_column(field: &OutputFieldV1) -> Result<(String, String), EvalFailure> {
    let r = field.r#ref.trim();
    let Some(path) = r.strip_prefix("$.") else {
        return Err(EvalFailure::InvalidTemplate(format!(
            "output_fields.ref must start with '$.' (got '{r}')"
        )));
    };
    let col_name = ref_to_column_name(path)?;
    let alias = if let Some(a) = field.alias.as_ref() {
        a.trim().to_string()
    } else {
        col_name
            .split("__")
            .last()
            .unwrap_or(col_name.as_str())
            .to_string()
    };
    if alias.is_empty() {
        return Err(EvalFailure::InvalidTemplate(format!(
            "output field alias empty for ref '{r}'"
        )));
    }
    Ok((col_name, alias))
}

fn anyvalue_to_json(v: AnyValue) -> Value {
    match v {
        AnyValue::Null => Value::Null,
        AnyValue::Boolean(b) => Value::Bool(b),
        AnyValue::Int8(i) => Value::Number((i as i64).into()),
        AnyValue::Int16(i) => Value::Number((i as i64).into()),
        AnyValue::Int32(i) => Value::Number((i as i64).into()),
        AnyValue::Int64(i) => Value::Number(i.into()),
        AnyValue::UInt8(i) => Value::Number((i as u64).into()),
        AnyValue::UInt16(i) => Value::Number((i as u64).into()),
        AnyValue::UInt32(i) => Value::Number((i as u64).into()),
        AnyValue::UInt64(i) => Value::Number((i as u64).into()),
        AnyValue::Float32(f) => serde_json::Number::from_f64(f as f64)
            .map(Value::Number)
            .unwrap_or(Value::Null),
        AnyValue::Float64(f) => serde_json::Number::from_f64(f)
            .map(Value::Number)
            .unwrap_or(Value::Null),
        AnyValue::String(s) => Value::String(s.to_string()),
        AnyValue::StringOwned(s) => Value::String(s.to_string()),
        other => Value::String(other.to_string()),
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use alert_runtime_common::{
        alert_executable_schema_version_v1, arrow_ipc_stream_base64_format_v1,
        evaluation_context_schema_version_v1, polars_eval_request_schema_version_v1,
        polars_eval_request_schema_version_v2, EvaluationContextInstanceV1, EvaluationContextRunV1,
        EvaluationContextV1, PartitionV1, TargetModeV1, TargetsV1, TriggerTypeV1,
    };
    use chrono::Utc;
    use polars::prelude::NamedFrom;
    use polars_io::ipc::IpcStreamWriter;
    use pretty_assertions::assert_eq;

    fn df_to_ipc_b64(df: &mut DataFrame) -> String {
        let mut buf: Vec<u8> = Vec::new();
        {
            let mut writer = IpcStreamWriter::new(&mut buf);
            writer.finish(df).unwrap();
        }
        BASE64.encode(buf)
    }

    #[test]
    fn evaluates_variable_placeholder_condition() {
        let mut df = DataFrame::new(vec![
            Series::new("target_key", ["ETH:mainnet:0xa", "ETH:mainnet:0xb"]),
            Series::new("ds_balance__balance_latest", [0.4_f64, 0.6_f64]),
        ])
        .unwrap();

        let frame_b64 = df_to_ipc_b64(&mut df);

        let tpl: AlertTemplateV1 = serde_json::from_value(serde_json::json!({
            "version": "v1",
            "name": "t",
            "description": "d",
            "alert_type": "wallet",
            "variables": [{"id":"threshold","type":"decimal","label":"Threshold","required":true}],
            "trigger": {"tx_type":"any","from":{"any_of":[],"labels":[],"not":[]},"to":{"any_of":[],"labels":[],"not":[]},"method":{"selector_any_of":[],"name_any_of":[],"required":false}},
            "datasources": [{"id":"ds_balance","catalog_id":"ducklake.wallet_balance_latest","bindings":{},"cache_ttl_secs":30,"timeout_ms":1500}],
            "enrichments": [],
            "conditions": {"all":[{"op":"lt","left":"$.datasources.ds_balance.balance_latest","right":"{{threshold}}"}],"any":[],"not":[]},
            "notification_template": {"title":"t","body":"b"},
            "action": {"notification_policy":"per_matched_target","cooldown_secs":0,"cooldown_key_template":"x","dedupe_key_template":"y"},
            "performance": {},
            "warnings": []
        }))
        .unwrap();

        let now = Utc::now();
        let eval_ctx = EvaluationContextV1 {
            schema_version: evaluation_context_schema_version_v1(),
            run: EvaluationContextRunV1 {
                run_id: "run".to_string(),
                attempt: 1,
                trigger_type: TriggerTypeV1::Periodic,
                enqueued_at: now,
                started_at: now,
            },
            instance: EvaluationContextInstanceV1 {
                instance_id: "inst".to_string(),
                user_id: Value::String("u1".to_string()),
                template_id: "tpl".to_string(),
                template_version: 1,
            },
            partition: PartitionV1 {
                network: "ETH".to_string(),
                subnet: "mainnet".to_string(),
                chain_id: 1,
            },
            schedule: None,
            targets: TargetsV1 {
                mode: TargetModeV1::Keys,
                group_id: None,
                keys: vec!["ETH:mainnet:0xa".to_string(), "ETH:mainnet:0xb".to_string()],
            },
            variables: serde_json::json!({"threshold": 0.5}),
            tx: None,
        };

        let req = PolarsEvalRequestV1 {
            schema_version: polars_eval_request_schema_version_v1(),
            request_id: "r".to_string(),
            job_id: "j".to_string(),
            run_id: "run".to_string(),
            template: tpl,
            evaluation_context: eval_ctx,
            frame: alert_runtime_common::ArrowFrameV1 {
                format: arrow_ipc_stream_base64_format_v1(),
                data: frame_b64,
            },
            output_fields: vec![OutputFieldV1 {
                r#ref: "$.datasources.ds_balance.balance_latest".to_string(),
                alias: Some("balance_latest".to_string()),
            }],
        };

        let resp = evaluate_request(&req, &EvalLimits::default());
        assert!(resp.error.is_none(), "unexpected error: {:?}", resp.error);
        assert_eq!(resp.matched.len(), 1);
        assert_eq!(resp.matched[0].target_key, "ETH:mainnet:0xa");
        assert_eq!(
            resp.matched[0].match_context["balance_latest"],
            serde_json::json!(0.4)
        );
    }

    #[test]
    fn evaluates_variable_placeholder_condition_v2_executable() {
        let mut df = DataFrame::new(vec![
            Series::new("target_key", ["ETH:mainnet:0xa", "ETH:mainnet:0xb"]),
            Series::new("ds_balance__balance_latest", [0.4_f64, 0.6_f64]),
        ])
        .unwrap();

        let frame_b64 = df_to_ipc_b64(&mut df);

        let exe: AlertExecutableV1 = serde_json::from_value(serde_json::json!({
            "schema_version": alert_executable_schema_version_v1(),
            "executable_id": "exe_1",
            "template": {"schema_version": "alert_template_v2", "template_id": "tpl_1", "fingerprint": "fp", "version": 1},
            "registry_snapshot": {"kind": "internal", "version": "v1", "hash": "h"},
            "target_kind": "wallet",
            "variables": [{"id":"threshold","type":"decimal","label":"Threshold","required":true}],
            "trigger_pruning": {"evm": {
                "chain_ids": [1],
                "tx_type": "any",
                "from": {"any_of": [], "labels": [], "not": []},
                "to": {"any_of": [], "labels": [], "not": []},
                "method": {"selector_any_of": [], "name_any_of": [], "required": false},
                "event": {"topic0_any_of": [], "name_any_of": [], "required": false}
            }},
            "datasources": [{"id":"ds_balance","catalog_id":"ducklake.wallet_balance_latest","bindings":{},"cache_ttl_secs":30,"timeout_ms":1500}],
            "enrichments": [],
            "conditions": {"all":[{"op":"lt","left":"$.datasources.ds_balance.balance_latest","right":"{{threshold}}"}],"any":[],"not":[]},
            "notification_template": {"title":"t","body":"b"},
            "action": {"notification_policy":"per_matched_target","cooldown_secs":0,"cooldown_key_template":"x","dedupe_key_template":"y"},
            "performance": {},
            "warnings": []
        }))
        .unwrap();

        let now = Utc::now();
        let eval_ctx = EvaluationContextV1 {
            schema_version: evaluation_context_schema_version_v1(),
            run: EvaluationContextRunV1 {
                run_id: "run".to_string(),
                attempt: 1,
                trigger_type: TriggerTypeV1::Periodic,
                enqueued_at: now,
                started_at: now,
            },
            instance: EvaluationContextInstanceV1 {
                instance_id: "inst".to_string(),
                user_id: Value::String("u1".to_string()),
                template_id: "tpl_1".to_string(),
                template_version: 1,
            },
            partition: PartitionV1 {
                network: "ETH".to_string(),
                subnet: "mainnet".to_string(),
                chain_id: 1,
            },
            schedule: None,
            targets: TargetsV1 {
                mode: TargetModeV1::Keys,
                group_id: None,
                keys: vec!["ETH:mainnet:0xa".to_string(), "ETH:mainnet:0xb".to_string()],
            },
            variables: serde_json::json!({"threshold": 0.5}),
            tx: None,
        };

        let req = PolarsEvalRequestV2 {
            schema_version: polars_eval_request_schema_version_v2(),
            request_id: "r".to_string(),
            job_id: "j".to_string(),
            run_id: "run".to_string(),
            executable: exe,
            evaluation_context: eval_ctx,
            frame: alert_runtime_common::ArrowFrameV1 {
                format: arrow_ipc_stream_base64_format_v1(),
                data: frame_b64,
            },
            output_fields: vec![OutputFieldV1 {
                r#ref: "$.datasources.ds_balance.balance_latest".to_string(),
                alias: Some("balance_latest".to_string()),
            }],
        };

        let resp = evaluate_request_v2(&req, &EvalLimits::default());
        assert!(resp.error.is_none(), "unexpected error: {:?}", resp.error);
        assert_eq!(resp.matched.len(), 1);
        assert_eq!(resp.matched[0].target_key, "ETH:mainnet:0xa");
        assert_eq!(
            resp.matched[0].match_context["balance_latest"],
            serde_json::json!(0.4)
        );
    }

    #[test]
    fn schema_mismatch_when_required_column_missing() {
        let mut df = DataFrame::new(vec![Series::new("target_key", ["ETH:mainnet:0xa"])]).unwrap();
        let frame_b64 = df_to_ipc_b64(&mut df);

        let tpl: AlertTemplateV1 = serde_json::from_value(serde_json::json!({
            "version": "v1",
            "name": "t",
            "description": "d",
            "alert_type": "wallet",
            "variables": [],
            "trigger": {"tx_type":"any","from":{"any_of":[],"labels":[],"not":[]},"to":{"any_of":[],"labels":[],"not":[]},"method":{"selector_any_of":[],"name_any_of":[],"required":false}},
            "datasources": [{"id":"ds_balance","catalog_id":"ducklake.wallet_balance_latest","bindings":{},"cache_ttl_secs":30,"timeout_ms":1500}],
            "enrichments": [],
            "conditions": {"all":[{"op":"gt","left":"$.datasources.ds_balance.balance_latest","right":0}],"any":[],"not":[]},
            "notification_template": {"title":"t","body":"b"},
            "action": {"notification_policy":"per_matched_target","cooldown_secs":0,"cooldown_key_template":"x","dedupe_key_template":"y"},
            "performance": {},
            "warnings": []
        }))
        .unwrap();

        let now = Utc::now();
        let eval_ctx = EvaluationContextV1 {
            schema_version: evaluation_context_schema_version_v1(),
            run: EvaluationContextRunV1 {
                run_id: "run".to_string(),
                attempt: 1,
                trigger_type: TriggerTypeV1::Periodic,
                enqueued_at: now,
                started_at: now,
            },
            instance: EvaluationContextInstanceV1 {
                instance_id: "inst".to_string(),
                user_id: Value::String("u1".to_string()),
                template_id: "tpl".to_string(),
                template_version: 1,
            },
            partition: PartitionV1 {
                network: "ETH".to_string(),
                subnet: "mainnet".to_string(),
                chain_id: 1,
            },
            schedule: None,
            targets: TargetsV1 {
                mode: TargetModeV1::Keys,
                group_id: None,
                keys: vec!["ETH:mainnet:0xa".to_string()],
            },
            variables: Value::Object(Default::default()),
            tx: None,
        };

        let req = PolarsEvalRequestV1 {
            schema_version: polars_eval_request_schema_version_v1(),
            request_id: "r".to_string(),
            job_id: "j".to_string(),
            run_id: "run".to_string(),
            template: tpl,
            evaluation_context: eval_ctx,
            frame: alert_runtime_common::ArrowFrameV1 {
                format: arrow_ipc_stream_base64_format_v1(),
                data: frame_b64,
            },
            output_fields: vec![],
        };

        let resp = evaluate_request(&req, &EvalLimits::default());
        let err = resp.error.expect("expected error");
        assert_eq!(err.code, "schema_mismatch");
    }
}
