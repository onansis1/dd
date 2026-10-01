# Into the Dead: Our Darkest Days - ammo recipe x5

`data_balancing` : 수정본 (탄약 레시피 산출량 x5, 재료 개수는 그대로 + 생존자 가방 칸 수 12 -> 24). 빌드 6000.5.11f1 기준.
적용: `StreamingAssets\AssetBundles\data_balancing` 원본을 백업한 뒤 이 파일로 교체.
재생성: `python3 mod.py <탄약배수> <가방칸수> <출력파일>` (patch.py가 이 빌드의 타입트리 헤더 28바이트를 건너뛰게 함; UnityPy 필요, P 경로 수정)

| 레시피 | 원래 | 수정 |
|---|---|---|
| PistolAmmo | 6 | 30 |
| PistolAmmo_MunitionsExpert | 9 | 45 |
| RevolverAmmo | 4 | 20 |
| RevolverAmmo_MunitionsExpert | 8 | 40 |
| RifleAmmo | 2 | 10 |
| RifleAmmo_MunitionsExpert | 3 | 15 |
| ShotgunAmmo | 2 | 10 |
| ShotgunAmmo_MunitionsExpert | 3 | 15 |
| AssaultRifleAmmo | 6 | 30 |
| AssaultRifleAmmo_MunitionsExpert | 9 | 45 |
