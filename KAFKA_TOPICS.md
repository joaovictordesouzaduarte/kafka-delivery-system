# Kafka Topics Configuration

## Overview

This document describes the Kafka topic creation for the delivery driver tracking system. The topic is configured to maintain only the **latest location** for each driver, using Kafka's log compaction feature.

## Topic: `driver-locations`

### Purpose

Store real-time location updates for delivery drivers. Only the most recent position per driver is retained.

### Key Configuration Strategy

- **Cleanup Policy**: `compact` - Kafka retains only the latest message per key (driver_id)
- **Replication Factor**: 3 - Data replicated across all brokers for fault tolerance
- **Partitions**: 3 - Enables parallel processing
- **Compression**: `snappy` - Efficient compression for network/storage optimization

---

## Create Topic Command

### Using kafka-topics.sh (Inside Kafka Container)

```bash
kafka-topics.sh --create \
  --bootstrap-server localhost:9092 \
  --topic driver-locations \
  --partitions 3 \
  --replication-factor 3 \
  --config cleanup.policy=compact \
  --config compression.type=snappy \
  --config min.cleanable.dirty.ratio=0.01 \
  --config segment.ms=10000 \
  --config delete.retention.ms=100
```

### Using Docker Compose Environment (Apache Kafka)

```bash
docker exec kafka1 /opt/kafka/bin/kafka-topics.sh --create \
  --bootstrap-server kafka1:9092 \
  --topic driver-locations \
  --partitions 3 \
  --replication-factor 3 \
  --config cleanup.policy=compact \
  --config compression.type=snappy \
  --config min.cleanable.dirty.ratio=0.01 \
  --config segment.ms=10000 \
  --config delete.retention.ms=100
```

---

## Configuration Parameters Explained


| Parameter                   | Value     | Description                                                                          |
| --------------------------- | --------- | ------------------------------------------------------------------------------------ |
| `cleanup.policy`            | `compact` | Keeps only the latest message for each key (driver_id). Old positions are discarded. |
| `partitions`                | `3`       | Number of partitions for parallel processing                                         |
| `replication-factor`        | `3`       | Each partition replicated across 3 brokers for fault tolerance                       |
| `compression.type`          | `snappy`  | Fast compression algorithm for better throughput                                     |
| `min.cleanable.dirty.ratio` | `0.01`    | Triggers compaction when 1% of log contains duplicate keys (aggressive compaction)   |
| `segment.ms`                | `10000`   | New log segment every 10 seconds (faster compaction eligibility)                     |
| `delete.retention.ms`       | `100`     | Tombstone records deleted after 100ms (for driver deletion scenarios)                |


---

## Verify Topic Creation

```bash
# List all topics
docker exec kafka1 /opt/kafka/bin/kafka-topics.sh --list \
  --bootstrap-server kafka1:9092

# Describe topic configuration
docker exec kafka1 /opt/kafka/bin/kafka-topics.sh --describe \
  --bootstrap-server kafka1:9092 \
  --topic driver-locations
```

---

## Message Key Strategy

**CRITICAL**: For log compaction to work properly, messages MUST be sent with `driver_id` as the key.

### Producer Message Format

```python
producer.send(
    topic='driver-locations',
    key=str(driver_id).encode('utf-8'),  # Key for compaction
    value=json.dumps({
        'driver_id': driver_id,
        'latitude': latitude,
        'longitude': longitude,
        'timestamp': timestamp,
        'status': status
    }).encode('utf-8')
)
```

---

## Why Log Compaction?

Log compaction ensures that:

- Kafka only retains the **latest location** for each driver
- Storage doesn't grow indefinitely with historical positions
- Redis always receives the current state
- System remains efficient for real-time tracking

### How It Works

```
Before Compaction:
driver_1 → {lat: 10.5, lon: 20.3, time: 10:00}
driver_1 → {lat: 10.6, lon: 20.4, time: 10:01}
driver_1 → {lat: 10.7, lon: 20.5, time: 10:02}

After Compaction:
driver_1 → {lat: 10.7, lon: 20.5, time: 10:02}  ← Only latest retained
```

---

## Additional Commands

### Delete Topic (if needed)

```bash
docker exec kafka1 /opt/kafka/bin/kafka-topics.sh --delete \
  --bootstrap-server kafka1:9092 \
  --topic driver-locations
```

### Alter Topic Configuration

```bash
docker exec kafka1 /opt/kafka/bin/kafka-configs.sh --alter \
  --bootstrap-server kafka1:9092 \
  --entity-type topics \
  --entity-name driver-locations \
  --add-config min.cleanable.dirty.ratio=0.05
```

---

## Testing Topic

### Produce Test Message

```bash
echo 'driver_123:{"driver_id":"driver_123","latitude":-23.550520,"longitude":-46.633308,"timestamp":"2026-03-07T10:00:00Z","status":"available"}' | \
docker exec -i kafka1 /opt/kafka/bin/kafka-console-producer.sh \
  --bootstrap-server kafka1:9092 \
  --topic driver-locations \
  --property "parse.key=true" \
  --property "key.separator=:"
```

### Consume Test Messages

```bash
docker exec kafka1 /opt/kafka/bin/kafka-console-consumer.sh \
  --bootstrap-server kafka1:9092 \
  --topic driver-locations \
  --from-beginning \
  --property print.key=true \
  --property key.separator=" => " \
  --max-messages 10
```

Then type:

```
driver_123:{"driver_id":"driver_123","latitude":-23.550520,"longitude":-46.633308,"timestamp":"2026-03-07T10:00:00Z","status":"available"}
```

### Consume Test Messages

```bash
docker exec -it kafka-1 kafka-console-consumer.sh \
  --bootstrap-server kafka-1:19092 \
  --topic driver-locations \
  --from-beginning \
  --property print.key=true \
  --property key.separator=" => "
```

---

## References

- [Kafka Log Compaction](https://kafka.apache.org/documentation/#compaction)
- [Topic Configuration](https://kafka.apache.org/documentation/#topicconfigs)

