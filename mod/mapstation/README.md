# 지도 스테이션: 처음부터 2명 보내기 (실험적)
MapStationDefinition 레벨 1(시작 상태)의 m_numSlots 1 -> 2. (업그레이드한 레벨 2는 원래 2)
사용 (게임/스팀 끄고): `py -3 patch_mapstation.py "<AssetBundles 경로>"`  (슬롯 수 변경: 끝에 숫자 추가)
이미 적용돼 있으면 변경 없음. 영입 섞기(shuffle_recruits.py)를 다시 돌려도 유지됨. 백업: data_balancing.mapbak
