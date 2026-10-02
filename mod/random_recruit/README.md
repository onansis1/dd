# 영입 생존자 무작위 섞기
`py -3 shuffle_recruits.py "<AssetBundles 경로>" [시드]` (게임/스팀 끄고 실행). 처음 실행할 때 data_balancing.bak 백업.

## 원리 (영입 후 NPC가 사라지는 문제를 해결한 방식)
장소 장면의 `Encounter`(NPC)는 `X_SurvivorExistence_NeitherList` 조건이 거짓이면 꺼집니다
(= 그 생존자가 쉘터/이탈 목록에 있으면 NPC 제거). 이 조건은 원래 그 장소의 생존자 X 를 가리켰기 때문에,
영입 결과만 섞으면 X 를 다른 곳에서 영입하는 순간 X 의 원래 장소가 꺼졌습니다.
이제 **영입 결과(RecruitmentData)와 장소 조건의 대상 생존자를 함께** 새 생존자로 바꿉니다.
그래서 생존자 Y 를 영입하면 'Y 가 서 있는 장소'의 NPC 가 사라지고, 다른 장소에는 영향이 없습니다. 추천 순서 같은 제약 없음.

## 범위
- 섞는 장소 11곳: Aubrey, Barb, Hudson, Isabel, Joe, Kirk, Lester, Michelle, Miguel, Rahul, Robbie
- 섞지 않음: Bowman(키 캐릭터), Candy / Christine / Frank / Vince (이 장소들은 다른 방식의 조건이라 아직 미확인), 인질, 스토리 전용.
  이미 섞인 상태여도 원래대로 복원합니다.
- 확인한 것: Barb 장소(Midtown_GasStation_02) 장면에서 위 조건을 직접 확인. 나머지 10곳은 같은 이름 규칙의 조건이 있는 것까지만 확인(장면은 미확인).
