# pipeline/spark/spark_streaming.py – Spark Structured Streaming jobs
import os
import json
import logging
from typing import Dict, List, Optional
from pyspark.sql import SparkSession
from pyspark.sql.functions import from_json, col, window, sum as spark_sum, count
from pyspark.sql.types import StructType, StructField, StringType, IntegerType, DoubleType, TimestampType

logger = logging.getLogger("crownstar.pipeline.spark")

class SparkStreamingJob:
    def __init__(self, app_name: str = "CrownStarStreaming", master: str = "local[*]"):
        self.spark = SparkSession.builder \
            .appName(app_name) \
            .master(master) \
            .config("spark.sql.streaming.checkpointLocation", "data/pipeline/spark_checkpoint") \
            .getOrCreate()
        self.streams = []
    
    def create_usage_aggregation_stream(self, kafka_bootstrap: str, input_topic: str, output_topic: str):
        """Stream: aggregate cost events per minute"""
        # Define schema for cost events
        schema = StructType([
            StructField("user_id", StringType()),
            StructField("tenant_id", StringType()),
            StructField("amount", DoubleType()),
            StructField("timestamp", TimestampType())
        ])
        # Read from Kafka
        df = self.spark.readStream \
            .format("kafka") \
            .option("kafka.bootstrap.servers", kafka_bootstrap) \
            .option("subscribe", input_topic) \
            .option("startingOffsets", "latest") \
            .load() \
            .select(from_json(col("value").cast("string"), schema).alias("data")) \
            .select("data.*")
        # Aggregate by window
        aggregated = df \
            .withWatermark("timestamp", "1 minute") \
            .groupBy(window(col("timestamp"), "1 minute"), col("tenant_id")) \
            .agg(spark_sum("amount").alias("total_cost"), count("*").alias("event_count"))
        # Write to Kafka
        query = aggregated.selectExpr("to_json(struct(*)) as value") \
            .writeStream \
            .format("kafka") \
            .option("kafka.bootstrap.servers", kafka_bootstrap) \
            .option("topic", output_topic) \
            .option("checkpointLocation", "data/pipeline/spark_checkpoint/cost_agg") \
            .outputMode("append") \
            .start()
        self.streams.append(query)
        logger.info(f"Started usage aggregation stream: {input_topic} -> {output_topic}")
        return query
    
    def create_conversation_embedding_stream(self, kafka_bootstrap: str, input_topic: str):
        """Stream: compute text embeddings from conversations (stub)"""
        # This would use a UDF with sentence-transformers
        schema = StructType([
            StructField("conversation_id", StringType()),
            StructField("user_message", StringType()),
            StructField("assistant_message", StringType()),
            StructField("timestamp", TimestampType())
        ])
        df = self.spark.readStream \
            .format("kafka") \
            .option("kafka.bootstrap.servers", kafka_bootstrap) \
            .option("subscribe", input_topic) \
            .load() \
            .select(from_json(col("value").cast("string"), schema).alias("data")) \
            .select("data.*")
        # In production, would call a UDF for embedding
        # For now, just print
        query = df.writeStream \
            .foreachBatch(lambda df, epoch: df.show(5)) \
            .start()
        self.streams.append(query)
        return query
    
    def stop_all(self):
        for q in self.streams:
            q.stop()
        self.spark.stop()
        logger.info("All Spark streams stopped")

_spark_job = None
def get_spark_job():
    global _spark_job
    if _spark_job is None:
        _spark_job = SparkStreamingJob()
    return _spark_job
