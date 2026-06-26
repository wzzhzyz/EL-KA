@echo off
chcp 65001 >nul
echo ============================================================
echo 安装实体链接智能体依赖
echo ============================================================

echo.
echo [1/3] 安装 Python 依赖...
pip install -r requirements.txt

echo.
echo [2/3] 下载 HanLP 和 BGE 模型...
python download_models.py

echo.
echo [3/3] 验证安装...
python -c "import fastapi, hanlp, sentence_transformers, faiss, fastcoref; print('✅ 所有依赖导入成功')"

echo.
echo ============================================================
echo 安装完成！
echo ============================================================
pause