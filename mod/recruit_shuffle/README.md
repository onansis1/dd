# 영입 생존자 위치 섞기 (실험적)
`data_balancing` = 기존 mod/data_balancing(총알 x5, 가방 24) + 일반 영입 16곳의 등장 생존자를 서로 섞음 (seed 7).
`AssetBundles\data_balancing`을 백업 후 교체. 다시 섞기: `python3 rec.py mod/data_balancing <시드> <출력>` (원본 data_config 경로는 스크립트 안 D 수정).
제외: 인질(Hostage_*), 스토리 전용(Hector, Kayla, Charlie, Cooper, Isaiah, Taylor, Otto, Eva, Issac).
