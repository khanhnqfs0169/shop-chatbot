@echo off
chcp 65001 > nul
echo ============================================
echo   SETUP CHATBOT FACEBOOK - SHOP THOI TRANG
echo ============================================
echo.
echo [1/3] Cai dat thu vien Python...
pip install flask anthropic requests python-dotenv openpyxl
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [LOI] Khong cai duoc! Kiem tra Python da duoc cai chua.
    echo       Tai Python tai: https://www.python.org/downloads/
    pause
    exit /b 1
)
echo.
echo [2/3] Tao file san pham mau (products.xlsx)...
python products_sample.py
echo.
echo [3/3] Kiem tra cai dat...
python -c "import flask, anthropic, openpyxl; print('Tat ca thu vien OK!')"
echo.
echo ============================================
echo   HOAN THANH! Buoc tiep theo:
echo ============================================
echo.
echo 1. Mo thu muc nay trong VS Code
echo 2. Copy ".env.example" thanh ".env"
echo 3. Dien Claude API Key va Facebook Token vao .env
echo 4. Mo products.xlsx va nhap san pham that cua shop
echo 5. Chay: python app.py
echo.
pause
