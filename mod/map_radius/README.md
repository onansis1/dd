# 은신처 탐색 반경(지도의 원) 넓히기 (실험적)
지도에서 은신처를 중심으로 그려지는 이동 가능 원의 크기는 data_levels > MapData 의 각 은신처 `m_scavengeRadius`(기본 987.5)와
갈 수 있는 장소 목록 `m_reachableLocations`(반경 안의 모든 장소로 미리 계산돼 있음, 18개 은신처 전부 일치 확인)로 정해집니다.
반경만 올리면 목록이 그대로라서 소용없어, 두 값을 함께 바꿉니다.

- `data_levels` : 바로 교체해서 쓰는 파일 (반경 x1.5 = 1481.2, 갈 수 있는 장소 평균 19.2 -> 34.7곳). 빌드 6000.5.11f1 의 data_levels 기준.
  `AssetBundles\data_levels` 를 백업한 뒤 교체.
- `widen_map_radius.py` : 배수를 바꿔 다시 만들 때. 설치된 data_levels 를 직접 고침 (백업 data_levels.bak 자동 생성).
  `py -3 widen_map_radius.py "<AssetBundles 경로>" 2.0`  (배수는 항상 기본 반경 기준이라 누적되지 않음)
검증: 수정본과 원본 비교 시 MapData 오브젝트 하나만 다르고 나머지 44,245개는 바이트까지 동일.
