@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo [go2w-quant] 首次运行：创建虚拟环境并安装依赖...
  python -m venv .venv
  ".venv\Scripts\python.exe" -m pip install --upgrade pip
  ".venv\Scripts\python.exe" -m pip install -r requirements.txt
)
if /i "%~1"=="--quant" (
  ".venv\Scripts\python.exe" quant.py %~2 %~3 %~4 %~5 %~6 %~7 %~8 %~9
) else if /i "%~1"=="--modeling" (
  ".venv\Scripts\python.exe" modeling.py %~2 %~3 %~4 %~5 %~6 %~7 %~8 %~9
) else if /i "%~1"=="--baseline" (
  ".venv\Scripts\python.exe" baseline.py %~2 %~3 %~4 %~5 %~6 %~7 %~8 %~9
) else if /i "%~1"=="--curvefit" (
  ".venv\Scripts\python.exe" curve_fit.py %~2 %~3 %~4 %~5 %~6 %~7 %~8 %~9
) else if /i "%~1"=="--backtest" (
  ".venv\Scripts\python.exe" backtest_rules.py %~2 %~3 %~4 %~5 %~6 %~7 %~8 %~9
  ".venv\Scripts\python.exe" backtest_engine.py %~2 %~3 %~4 %~5 %~6 %~7 %~8 %~9
) else (
  ".venv\Scripts\python.exe" summary.py %*
)
endlocal