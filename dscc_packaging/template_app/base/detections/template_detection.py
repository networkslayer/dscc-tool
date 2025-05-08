# Databricks notebook source
# MAGIC %md
# MAGIC ### Detection Metadata
# MAGIC ```yaml
# MAGIC dscc:
# MAGIC   author: Derek King
# MAGIC   created: 2025-03-24
# MAGIC   modified: 2025-03-24
# MAGIC   version: 1.0.0
# MAGIC   source: databricks
# MAGIC   sourcetype: access_audit
# MAGIC   content_type: detection
# MAGIC   detection:
# MAGIC     name: access_token_created
# MAGIC     description: Detects when a new access token is created.
# MAGIC     fidelity: high
# MAGIC     category: access
# MAGIC     objective:
# MAGIC       - Detect when a new access token is created.
# MAGIC     false_positives:
# MAGIC       - A new access token was created by a legitimate user.
# MAGIC     severity: high
# MAGIC     validation:
# MAGIC       - The user who created the access token is a legitimate user.
# MAGIC       - The user who created the access token has a legitimate reason to create the access token.
# MAGIC tests:
# MAGIC   - data: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
# MAGIC ```

# COMMAND ----------

# your detection logic goes here
