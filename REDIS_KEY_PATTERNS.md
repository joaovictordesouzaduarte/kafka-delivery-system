# Redis Key Patterns - Explanation

## Current Setup (Default)

Our connector uses the **default key mapping**:

```json
{
  "config": {
    "topics": "driver-locations"
    // NO redis.key.pattern configured
  }
}
```

**Behavior**: Redis key = Kafka message key (directly)

### Example

**Kafka Message:**
- Topic: `driver-locations`
- Key: `driver_123`
- Value: `{"driver_id":"driver_123","latitude":-23.550520,...}`

**Stored in Redis:**
```
Key:   driver_123
Value: {"driver_id":"driver_123","latitude":-23.550520,...}
```

**Access:**
```bash
docker exec my-redis redis-cli GET "driver_123"
```

---

## Alternative: Custom Key Pattern

If you wanted more structured keys, you could configure:

```json
{
  "config": {
    "topics": "driver-locations",
    "redis.key.pattern": "driver:${topic}:${key}"
  }
}
```

### Pattern Variables

| Variable | Meaning | Example |
|----------|---------|---------|
| `${topic}` | Kafka topic name | `driver-locations` |
| `${key}` | Kafka message key | `driver_123` |
| `${partition}` | Partition number | `0`, `1`, `2` |
| Literal text | Fixed string | `driver`, `app`, `prefix` |

### Example with Custom Pattern

**Pattern**: `driver:${topic}:${key}`

**Kafka Message:**
- Topic: `driver-locations`
- Key: `driver_123`

**Stored in Redis:**
```
Key:   driver:driver-locations:driver_123
Value: {"driver_id":"driver_123","latitude":-23.550520,...}
```

**Access:**
```bash
docker exec my-redis redis-cli GET "driver:driver-locations:driver_123"
```

---

## Pattern Breakdown: `driver:${topic}:${key}`

```
driver : driver-locations : driver_123
  ↓            ↓                ↓
Literal    Topic Name     Kafka Message Key
String    (variable)        (variable)
```

### Why Use Custom Patterns?

1. **Namespacing**: Separate different types of data
   ```
   driver:driver-locations:driver_123
   order:order-events:order_456
   payment:payment-status:payment_789
   ```

2. **Organization**: Group related keys
   ```bash
   # Find all driver keys
   redis-cli KEYS "driver:*"
   
   # Find all keys from specific topic
   redis-cli KEYS "driver:driver-locations:*"
   ```

3. **Multi-topic connectors**: If one connector handles multiple topics
   ```json
   {
     "topics": "driver-locations,driver-status,driver-orders"
   }
   ```
   Keys would be:
   ```
   app:driver-locations:driver_123
   app:driver-status:driver_123
   app:driver-orders:order_456
   ```

---

## Current vs Custom Pattern Comparison

### Scenario: Multiple location updates for driver_123

**Current Configuration (Default)**
```
Redis Keys:
  driver_123 → latest location

Simple and clean!
```

**With Pattern: `driver:${topic}:${key}`**
```
Redis Keys:
  driver:driver-locations:driver_123 → latest location

More verbose but organized!
```

**With Pattern: `app:${topic}:${key}`**
```
Redis Keys:
  app:driver-locations:driver_123 → latest location

Good for multi-application Redis!
```

---

## When to Use Each Approach

### Use Default (Current Setup) When:
- ✅ Single application using Redis
- ✅ Simple key names (like driver_123)
- ✅ No namespace conflicts
- ✅ Want simplicity

### Use Custom Pattern When:
- ✅ Multiple applications share Redis
- ✅ Multiple topics → same connector
- ✅ Need organized key structure
- ✅ Want to query by topic/prefix

---

## Changing the Pattern

If you want to add a custom pattern:

1. **Update connector config:**
```json
{
  "name": "redis-sink-driver-locations",
  "config": {
    "connector.class": "com.github.jcustenborder.kafka.connect.redis.RedisSinkConnector",
    "tasks.max": "3",
    "topics": "driver-locations",
    "redis.hosts": "my-redis:6379",
    "redis.database": "0",
    "redis.key.pattern": "driver:${topic}:${key}",  // <-- ADD THIS
    "key.converter": "org.apache.kafka.connect.storage.StringConverter",
    "value.converter": "org.apache.kafka.connect.storage.StringConverter"
  }
}
```

2. **Redeploy:**
```bash
# Delete old connector
curl -X DELETE http://localhost:8083/connectors/redis-sink-driver-locations

# Deploy new config
curl -X POST http://localhost:8083/connectors \
  -H "Content-Type: application/json" \
  -d @redis-sink-connector.json
```

3. **Access data:**
```bash
# Old way (before pattern)
docker exec my-redis redis-cli GET "driver_123"

# New way (with pattern)
docker exec my-redis redis-cli GET "driver:driver-locations:driver_123"
```

---

## Recommendation for Your Project

**Keep the default (current) setup** because:
- Simple driver IDs as keys (`driver_123`)
- Single topic (`driver-locations`)
- Easy to query: `redis-cli GET driver_123`
- No namespace conflicts

Only add a pattern if you:
- Add more topics later
- Share Redis with other applications
- Need advanced key organization

---

## Current Working Commands

```bash
# List all drivers
docker exec my-redis redis-cli KEYS "driver_*"

# Get specific driver
docker exec my-redis redis-cli GET "driver_123"

# Get all driver locations
for key in $(docker exec my-redis redis-cli KEYS "driver_*"); do
  echo "=== $key ==="
  docker exec my-redis redis-cli GET "$key"
done
```
