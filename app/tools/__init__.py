from app.tools.register import register_tool
from app.tools.schemas import ANALYZE_JD_SCHEMA
from app.tools.jd_tools import analyze_jd_requirements

register_tool(ANALYZE_JD_SCHEMA, analyze_jd_requirements)
