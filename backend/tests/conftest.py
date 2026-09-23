import os
import tempfile

# 必须在导入 app.main 之前指到临时 SQLite，避免连 PostgreSQL
_tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_tmp_db.close()
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp_db.name}"
