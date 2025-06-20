# 📚 Ekko CE - Documentation Index

## 🎯 **OVERVIEW**

This is the comprehensive documentation index for Ekko CE (Community Edition), a blockchain monitoring and alerting platform. All documentation is designed to help developers onboard quickly and maintain the system effectively.

---

## 🚀 **GETTING STARTED**

### **For New Developers**
1. **[Developer Onboarding](./DEVELOPER_ONBOARDING.md)** 📖
   - 30-minute quick start guide
   - Project structure overview
   - Development workflow
   - Common tasks and debugging

### **For System Administrators**
2. **[Service Specifications](./SERVICE_SPECIFICATIONS.md)** 🏗️
   - Complete system architecture
   - Service responsibilities
   - Data flow diagrams
   - Deployment configuration

---

## 🔌 **API & INTEGRATION**

### **REST API Documentation**
3. **[API Reference](./API_REFERENCE.md)** 🔌
   - Complete endpoint documentation
   - Request/response schemas
   - Authentication methods
   - Error handling

### **Messaging & Communication**
4. **[NATS Subjects Reference](./NATS_SUBJECTS_REFERENCE.md)** 📡
   - Message schemas and patterns
   - Subject naming conventions
   - JetStream configuration
   - Inter-service communication

---

## 🗄️ **DATA & STORAGE**

### **Database Architecture**
5. **[Database Schema](./DATABASE_SCHEMA.md)** 🗄️
   - DuckDB table structures
   - NATS KV bucket schemas
   - MinIO Delta Lake organization
   - Data synchronization patterns

---

## 🎯 **FEATURE DOCUMENTATION**

### **Alert System**
- **Natural Language Processing**: DSPy-powered parameter inference
- **Polars DSL Execution**: High-performance data queries
- **Real-time Processing**: NATS-based message handling
- **Background Tasks**: FastAPI integration

### **Multi-Network Support**
- **Avalanche**: C-Chain and subnet support
- **Ethereum**: Mainnet and testnet compatibility
- **Extensible Architecture**: Easy addition of new networks

### **Data Pipeline**
- **Real-time Fetching**: Blockchain data collection
- **Delta Lake Storage**: Versioned data management
- **Analytics Engine**: DuckDB-powered queries

---

## 📋 **QUICK REFERENCE**

### **Service Ports**
| Service | Port | Purpose |
|---------|------|---------|
| API | 8000 | REST API endpoints |
| Dashboard | 3000 | Web interface |
| NATS | 4222 | Message broker |
| MinIO API | 9000 | Object storage |
| MinIO Console | 9001 | Storage management |

### **Key Endpoints**
```bash
# Health check
GET http://localhost:8000/

# Alert executor stats
GET http://localhost:8000/alerts/executor/stats

# Test alert execution
POST http://localhost:8000/alerts/test-execution

# API documentation
GET http://localhost:8000/docs
```

### **Docker Commands**
```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f api

# Rebuild service
docker-compose build api && docker-compose restart api

# Check status
docker-compose ps
```

---

## 🔧 **DEVELOPMENT WORKFLOWS**

### **Adding New Features**
1. **Backend Changes**: Edit `api/app/` files
2. **Frontend Changes**: Edit `dashboard/src/` files
3. **Pipeline Changes**: Edit `pipeline/src/` files
4. **Documentation**: Update relevant docs

### **Testing Procedures**
1. **Unit Tests**: Service-specific test suites
2. **Integration Tests**: Cross-service functionality
3. **API Tests**: Endpoint validation
4. **Load Tests**: Performance verification

### **Deployment Process**
1. **Development**: Local Docker Compose
2. **Staging**: Container orchestration
3. **Production**: Scalable deployment
4. **Monitoring**: Health checks and metrics

---

## 🎯 **ARCHITECTURE PATTERNS**

### **Message-Driven Architecture**
- **NATS JetStream**: Reliable message delivery
- **Event Sourcing**: Audit trail and replay capability
- **CQRS**: Command/Query separation

### **Data Storage Strategy**
- **Hot Data**: DuckDB for fast analytics
- **Warm Data**: NATS KV for real-time state
- **Cold Data**: MinIO Delta Lake for archival

### **Microservices Design**
- **API Service**: Business logic and REST endpoints
- **Pipeline Service**: Data collection and processing
- **Alert Executor**: Background task processing
- **Dashboard**: User interface and visualization

---

## 📊 **MONITORING & OBSERVABILITY**

### **Health Checks**
- Service availability monitoring
- Database connectivity verification
- Message broker status tracking

### **Logging Strategy**
- Structured logging across all services
- Centralized log aggregation
- Error tracking and alerting

### **Performance Metrics**
- API response times
- Message processing rates
- Database query performance
- Resource utilization

---

## 🔐 **SECURITY CONSIDERATIONS**

### **Authentication & Authorization**
- JWT token-based authentication
- Role-based access control
- API key management

### **Data Protection**
- Encryption at rest and in transit
- Secure configuration management
- Input validation and sanitization

### **Network Security**
- Service-to-service communication
- Container network isolation
- External API security

---

## 🚀 **SCALING & PERFORMANCE**

### **Horizontal Scaling**
- Multiple API service instances
- Load balancing strategies
- Database read replicas

### **Vertical Scaling**
- Resource allocation optimization
- Memory and CPU tuning
- Storage performance optimization

### **Caching Strategies**
- Redis for session management
- DuckDB query result caching
- NATS KV for real-time data

---

## 📝 **MAINTENANCE PROCEDURES**

### **Regular Maintenance**
- Database cleanup and optimization
- Log rotation and archival
- Security updates and patches

### **Backup & Recovery**
- Database backup procedures
- Configuration backup
- Disaster recovery planning

### **Troubleshooting**
- Common issue resolution
- Debug logging procedures
- Performance optimization

---

## 🎉 **CONCLUSION**

This documentation provides comprehensive coverage of the Ekko CE platform, from quick start guides to detailed architectural specifications. The modular design and clear documentation make it easy for new developers to contribute and for the system to evolve over time.

### **Next Steps**
1. Start with **[Developer Onboarding](./DEVELOPER_ONBOARDING.md)** for immediate productivity
2. Review **[Service Specifications](./SERVICE_SPECIFICATIONS.md)** for architectural understanding
3. Use **[API Reference](./API_REFERENCE.md)** for integration work
4. Consult other documents as needed for specific tasks

**Happy developing!** 🚀

---

## 📞 **Support & Community**

- **Documentation Issues**: Create GitHub issues for doc improvements
- **Feature Requests**: Submit enhancement proposals
- **Bug Reports**: Use issue templates for consistent reporting
- **Community**: Join discussions and share experiences

This living documentation evolves with the platform to ensure it remains accurate and useful for all contributors.
