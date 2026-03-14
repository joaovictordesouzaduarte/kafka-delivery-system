# Redis Sink Connector Configuration

## Working Configuration

The Redis Sink Connector is successfully configured and running. It automatically reads driver location updates from Kafka and stores the latest state in Redis.

### Connector Configuration File

**File**: `redis-sink-connector.json`

```json
{
  "name": "redis-sink-driver-locations",
  "config": {
    "connector.class": "com.github.jcustenborder.kafka.connect.redis.RedisSinkConnector",
    "tasks.max": "3",
    "topics": "driver-locations",
    "redis.hosts": "my-redis:6379",
    "redis.database": "0",
    "key.converter": "org.apache.kafka.connect.storage.StringConverter",
    "value.converter": "org.apache.kafka.connect.storage.StringConverter"
  }
}
```

### Key Configuration Points


| Parameter         | Value                                                             | Explanation                                                                                      |
| ----------------- | ----------------------------------------------------------------- | ------------------------------------------------------------------------------------------------ |
| `connector.class` | `com.github.jcustenborder.kafka.connect.redis.RedisSinkConnector` | The jcustenborder Redis connector (installed via Confluent Hub)                                  |
| `tasks.max`       | `3`                                                               | Three parallel tasks for processing                                                              |
| `topics`          | `driver-locations`                                                | Kafka topic to consume from                                                                      |
| `redis.hosts`     | `my-redis:6379`                                                   | Redis server address (internal Docker network)                                                   |
| `value.converter` | `StringConverter`                                                 | **IMPORTANT**: Must use StringConverter (not JsonConverter) - the connector expects String/Bytes |


### Common Error Fixed

**Original Error**:

```
DataException: The value for the record must be String or Bytes
```

**Solution**: Changed from `JsonConverter` to `StringConverter`. The connector stores the JSON as a string in Redis, which is exactly what we need.

---

## Deploy the Connector

### 1. Create/Update the Connector

```bash
curl -X POST http://localhost:8083/connectors \
  -H "Content-Type: application/json" \
  -d @redis-sink-connector.json
```

### 2. Check Connector Status

```bash
curl http://localhost:8083/connectors/redis-sink-driver-locations/status
```

Expected output:

```json
{
  "name": "redis-sink-driver-locations",
  "connector": {"state": "RUNNING", ...},
  "tasks": [
    {"id": 0, "state": "RUNNING", ...},
    {"id": 1, "state": "RUNNING", ...},
    {"id": 2, "state": "RUNNING", ...}
  ],
  "type": "sink"
}
```

### 3. Delete Connector (if needed)

```bash
curl -X DELETE http://localhost:8083/connectors/redis-sink-driver-locations
```

---

## Test the Pipeline

### Send Test Data

```bash
cat << 'EOF' | docker exec -i kafka1 /opt/kafka/bin/kafka-console-producer.sh \
  --bootstrap-server kafka1:9092 \
  --topic driver-locations \
  --property "parse.key=true" \
  --property "key.separator=:"
driver_123:{"driver_id":"driver_123","latitude":-23.550520,"longitude":-46.633308,"timestamp":"2026-03-07T10:00:00Z","status":"available"}
driver_456:{"driver_id":"driver_456","latitude":-23.560000,"longitude":-46.640000,"timestamp":"2026-03-07T10:00:00Z","status":"busy"}
EOF
```

### Verify in Redis

```bash
# List all driver keys
docker exec my-redis redis-cli KEYS "driver_*"

# Get specific driver location
docker exec my-redis redis-cli GET driver_123

# Get all drivers
docker exec my-redis redis-cli --scan --pattern "driver_*" | \
  xargs -I {} docker exec my-redis redis-cli GET {}
```

Expected output:

```json
{"driver_id":"driver_123","latitude":-23.550520,"longitude":-46.633308,"timestamp":"2026-03-07T10:00:00Z","status":"available"}
```

---

## How It Works

### Data Flow

```
Python Producer
    ↓
    ↓ (sends JSON with driver_id as key)
    ↓
Kafka Topic: driver-locations
    ↓
    ↓ (Kafka Connect consumes)
    ↓
Redis Sink Connector (3 tasks)
    ↓
    ↓ (stores as key-value)
    ↓
Redis Database
    Key: driver_123
    Value: {"driver_id":"driver_123","latitude":...}
```

### Redis Key-Value Mapping

- **Key**: The message key from Kafka (e.g., `driver_123`)
- **Value**: The JSON string (e.g., `{"driver_id":"driver_123","latitude":-23.550520,...}`)

### State Management

When multiple updates arrive for the same driver:

1. Kafka receives all messages (with same key)
2. Log compaction (configured on topic) will eventually keep only latest per key
3. Redis Sink Connector processes messages and **overwrites** the Redis key
4. Redis always contains the **most recent** state for each driver

---

## Monitoring

### Check Connector Logs

```bash
# Real-time logs
docker logs -f kafka-connect | grep redis

# Last 50 lines
docker logs kafka-connect --tail 50
```

### Check Consumer Group

```bash
docker exec kafka1 /opt/kafka/bin/kafka-consumer-groups.sh \
  --bootstrap-server kafka1:9092 \
  --describe \
  --group connect-redis-sink-driver-locations
```

### Check Redis Memory Usage

```bash
docker exec my-redis redis-cli INFO memory
```

---

## Troubleshooting

### Connector Not Running

```bash
# Check status
curl http://localhost:8083/connectors/redis-sink-driver-locations/status

# Restart connector
curl -X POST http://localhost:8083/connectors/redis-sink-driver-locations/restart

# Restart specific task
curl -X POST http://localhost:8083/connectors/redis-sink-driver-locations/tasks/0/restart
```

### Messages in Kafka but Not in Redis

1. Check connector logs: `docker logs kafka-connect --tail 100`
2. Verify Redis connection: `docker exec my-redis redis-cli PING`
3. Check consumer group lag: See "Check Consumer Group" above

### Clear Redis Data

```bash
# Delete specific driver
docker exec my-redis redis-cli DEL driver_123

# Delete all driver keys
docker exec my-redis redis-cli --scan --pattern "driver_*" | \
  xargs docker exec my-redis redis-cli DEL

# Flush entire database (CAREFUL!)
docker exec my-redis redis-cli FLUSHDB
```

---

## Production Considerations

1. **Monitoring**: Set up alerts for connector failures
2. **Scaling**: Increase `tasks.max` for higher throughput
3. **TTL**: Consider adding Redis TTL for inactive drivers
4. **Security**: Add Redis authentication in production
5. **Backups**: Configure Redis persistence (RDB/AOF)

---

## Success Criteria ✅

- Connector class correctly configured
- StringConverter used for values
- 3 tasks running in parallel
- Messages flow from Kafka to Redis
- Redis stores latest state per driver
- Key-value mapping works correctly

