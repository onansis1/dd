# Survivor Draw (생존자 · 쉘터 뽑기)
`SurvivorDraw.exe` 더블클릭 → 브라우저에 뽑기 화면이 열립니다. 창(탭)을 닫으면 프로그램도 종료됩니다.
후보 19명: Bowman, Cooper, Isaiah, Charlie, Hao, Kayla, Mei, Daphne, Dianne, Hector, Tracy, Otto, Leo, Sebastian, Taylor, Wayne, Eva, Penny, Darrel
- 1~19명 뽑기(중복 없음), 이름 클릭으로 후보 제외/복귀, Space/Enter로 뽑기
- 이름을 바꾸려면 index.html의 NAMES 배열 수정 후 `GOOS=windows GOARCH=amd64 go build -ldflags "-s -w -H=windowsgui" -o SurvivorDraw.exe .`
- 서명 없는 exe라 Windows SmartScreen/백신 경고가 뜰 수 있습니다 (더 알아보기 → 실행).

## 쉘터 뽑기
뽑기 버튼 하나로 생존자와 쉘터를 동시에 뽑습니다. '쉘터도 같이 뽑기' 체크로 켜고 끄고, 생존자를 0명으로 두면 쉘터만 뽑습니다.
쉘터 후보 16곳: 광저우 웍, 릴 브롱코스 어린이집, 슈레더 스트리트 319번지, 갤럭시 존 오락실, 메이 이모의 트럭 기사 식당, 밸류 레코드, 베스트 일렉트로닉스, 스탠튼 & 선 정육점, 스프링우드 드라이브 22번지, 서티 오트 식스 바, 애쉬비 수집광의 집, 에버턴가 14번지, 킨스키 재단 갤러리, 텍사스 스포츠용품점, 텍스웨이 주유소 하트 스트리트, 피츠제럴드의 집
(index.html 의 SHELTERS 배열 수정 후 재빌드)
