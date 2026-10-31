# 조화의영약_4종 레시피

검은사막 조화의 영약(아인 · 카마실비아 · 인간 · 에다니아) 재료 체크리스트·레시피 도우미.
제작 목표 횟수로 타이머를 돌리고, 끝나기 전/끝났을 때 카카오톡(나에게 보내기)으로 알림을 보냅니다.

## 설치
[Releases](../../releases/latest) 에서 `HarmonyElixirSetup.exe` 를 받아 실행하세요. (관리자 권한 불필요)
이후 업데이트는 프로그램이 자동으로 확인하고, 새 버전이 있으면 안내합니다.

## 개발
```
pip install requests pillow pyinstaller
python app.py
```
카카오 알림을 쓰려면 `kakao_config.example.py` 를 `kakao_config.py` 로 복사해 REST API 키를 입력합니다.
(Redirect URI `http://localhost:8765/callback`, 동의항목 `talk_message`)

## 빌드 / 배포
```
build.bat        -> installer_output\HarmonyElixirSetup.exe
```
`app_core.py` 의 `CURRENT_VERSION` 을 올리고 빌드한 뒤, GitHub Release(태그 `vX.Y.Z`)에 `HarmonyElixirSetup.exe` 를 첨부하면 사용자 앱이 자동 업데이트합니다.

저장 데이터: `%APPDATA%\HarmonyElixirRecipe` (업데이트/재설치해도 유지)
