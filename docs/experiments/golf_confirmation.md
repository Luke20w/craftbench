# Golf confirmation: parent vs golfed copy, 6 runs each per change request

Positive % = golfed rated HARDER (correct: same behaviour, less readable). p = one-sided permutation test that golfed > parent.

| measure | CR | parent mean (runs) | golfed mean (runs) | golfed vs parent | p |
|---|---|---|---|---|---|
| score | limits | 1.00 [1.0, 1.0, 1.0, 1.0, 1.0, 1.0] | 1.00 [1.0, 1.0, 1.0, 1.0, 1.0, 1.0] | +0% | nan |
| score | subpipelines | 1.00 [1.0, 1.0, 1.0, 1.0, 1.0, 1.0] | 0.97 [0.94, 1.0, 1.0, 0.94, 0.94, 1.0] | -3% | nan |
| read_to_tts | limits | 5076 [5020, 5144, 5089, 5126, 5089, 4984] | 2529 [4168, 2144, 2102, 2312, 2250, 2197] | -50% | 1.000 |
| read_to_tts | subpipelines | 6035 [5427, 7228, 5478, 6989, 5463, 5628] | 4685 [3263, 5227, 5189, 5069, 4640, 4720] | -22% | 1.000 |
| nodes_read_to_tts | limits | 5076 [5020, 5144, 5089, 5126, 5089, 4984] | 4544 [7482, 3900, 3858, 4068, 4005, 3953] | -10% | 0.717 |
| nodes_read_to_tts | subpipelines | 6035 [5427, 7228, 5478, 6989, 5463, 5628] | 8252 [5725, 9228, 9105, 9018, 8152, 8283] | +37% | 0.005 |
| read_per_test | limits | 4253 [4192, 4302, 4277, 4309, 4277, 4162] | 2218 [4168, 1774, 1816, 1918, 1814, 1819] | -48% | 0.999 |
| read_per_test | subpipelines | 5876 [5366, 7119, 5373, 6534, 5357, 5508] | 4295 [3359, 2811, 5137, 5157, 4795, 4511] | -27% | 1.000 |
| nodes_read_per_test | limits | 4253 [4192, 4302, 4277, 4309, 4277, 4162] | 4015 [7482, 3267, 3313, 3410, 3306, 3311] | -6% | 0.534 |
| nodes_read_per_test | subpipelines | 5876 [5366, 7119, 5373, 6534, 5357, 5508] | 7553 [5895, 4831, 9054, 9193, 8408, 7938] | +29% | 0.033 |
