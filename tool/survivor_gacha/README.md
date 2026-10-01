# Survivor Draw (생존자 뽑기)
`SurvivorDraw.exe` 더블클릭 → 브라우저에 뽑기 화면이 열립니다. 창(탭)을 닫으면 프로그램도 종료됩니다.
후보 19명: Bowman, Cooper, Isaiah, Charlie, Hao, Kayla, Mei, Daphne, Dianne, Hector, Tracy, Otto, Leo, Sebastian, Taylor, Wayne, Eva, Penny, Darrel
- 1~19명 뽑기(중복 없음), 이름 클릭으로 후보 제외/복귀, Space/Enter로 뽑기
- 이름을 바꾸려면 index.html의 NAMES 배열 수정 후 `GOOS=windows GOARCH=amd64 go build -ldflags "-s -w -H=windowsgui" -o SurvivorDraw.exe .`
- 서명 없는 exe라 Windows SmartScreen/백신 경고가 뜰 수 있습니다 (더 알아보기 → 실행).
