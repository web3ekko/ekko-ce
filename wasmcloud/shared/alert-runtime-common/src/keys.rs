use serde::{Deserialize, Serialize};

/// Canonical `{network}:{subnet}` identifier (e.g., `ETH:mainnet`).
#[derive(Debug, Clone, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub struct NetworkSubnetKey(pub String);

impl NetworkSubnetKey {
    pub fn new(network: &str, subnet: &str) -> Self {
        Self(format!("{}:{}", network, subnet))
    }
}

/// Canonical `{network}:{subnet}:{address_or_slug...}` identifier.
///
/// For v1 alert execution, wallet and contract targets use:
/// - `ETH:mainnet:0xabc...`
#[derive(Debug, Clone, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub struct TargetKey(pub String);

impl TargetKey {
    pub fn new(network: &str, subnet: &str, id: &str) -> Self {
        Self(format!("{}:{}:{}", network, subnet, id))
    }

    pub fn as_str(&self) -> &str {
        &self.0
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use pretty_assertions::assert_eq;

    #[test]
    fn test_network_subnet_key_format() {
        let key = NetworkSubnetKey::new("ETH", "mainnet");
        assert_eq!(key.0, "ETH:mainnet");
    }

    #[test]
    fn test_target_key_format() {
        let key = TargetKey::new("ETH", "mainnet", "0xabc");
        assert_eq!(key.0, "ETH:mainnet:0xabc");
    }
}
