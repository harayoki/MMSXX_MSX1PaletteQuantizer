| グループ | アセンブリ | バイト列 (16進) | バイト数 | 補足 |
| :--- | :--- | :--- | :--- | :--- |
| **制御/単バイト命令** | `NOP` | `00` | 1 | 無操作 |
| | `EX AF, AF'` | `08` | 1 | 予備レジスタセットと交換 |
| | `DJNZ e` | `10 e` | 2 | Bをデクリメントし非ゼロなら相対ジャンプ |
| | `JR e` | `18 e` | 2 | 無条件相対ジャンプ |
| | `JR NZ,e` | `20 e` | 2 | Z=0のとき相対ジャンプ |
| | `JR Z,e` | `28 e` | 2 | Z=1のとき相対ジャンプ |
| | `JR NC,e` | `30 e` | 2 | C=0のとき相対ジャンプ |
| | `JR C,e` | `38 e` | 2 | C=1のとき相対ジャンプ |
| | `RLCA` | `07` | 1 | Aレジスタの左ローテート（キャリー経由なし） |
| | `RRCA` | `0F` | 1 | Aレジスタの右ローテート（キャリー経由なし） |
| | `RLA` | `17` | 1 | Aレジスタの左ローテート（キャリー経由） |
| | `RRA` | `1F` | 1 | Aレジスタの右ローテート（キャリー経由） |
| | `DAA` | `27` | 1 | 2進化10進補正 |
| | `CPL` | `2F` | 1 | Aレジスタをビット反転 |
| | `SCF` | `37` | 1 | キャリーフラグセット |
| | `CCF` | `3F` | 1 | キャリーフラグ反転 |
| | `HALT` | `76` | 1 | クロックが停止し割り込み待ち |
| | `EX DE,HL` | `EB` | 1 | DEとHLを交換 |
| | `EX (SP),HL` | `E3` | 1 | スタックトップとHLを交換 |
| | `EX AF,AF'` | `08` | 1 | 予備レジスタセットと交換 |
| | `DI` | `F3` | 1 | 割り込み禁止 |
| | `EI` | `FB` | 1 | 割り込み許可 |
| **8ビットロード (即値)** | `LD B,n` | `06 n` | 2 | B <- n |
| | `LD C,n` | `0E n` | 2 | C <- n |
| | `LD D,n` | `16 n` | 2 | D <- n |
| | `LD E,n` | `1E n` | 2 | E <- n |
| | `LD H,n` | `26 n` | 2 | H <- n |
| | `LD L,n` | `2E n` | 2 | L <- n |
| | `LD (HL),n` | `36 n` | 2 | (HL) <- n |
| | `LD A,n` | `3E n` | 2 | A <- n |
| **8ビットロード (BC/DE間接)** | `LD (BC),A` | `02` | 1 | (BC) <- A |
| | `LD A,(BC)` | `0A` | 1 | A <- (BC) |
| | `LD (DE),A` | `12` | 1 | (DE) <- A |
| | `LD A,(DE)` | `1A` | 1 | A <- (DE) |
| **8ビットロード (レジスタ間 $LD r, r'$ )** | `LD B, B` | `40` | 1 | B <- B |
| | `LD B, C` | `41` | 1 | B <- C |
| | `LD B, D` | `42` | 1 | B <- D |
| | `LD B, E` | `43` | 1 | B <- E |
| | `LD B, H` | `44` | 1 | B <- H |
| | `LD B, L` | `45` | 1 | B <- L |
| | `LD B, (HL)` | `46` | 1 | B <- (HL) |
| | `LD B, A` | `47` | 1 | B <- A |
| | `LD C, B` | `48` | 1 | C <- B |
| | `LD C, C` | `49` | 1 | C <- C |
| | `LD C, D` | `4A` | 1 | C <- D |
| | `LD C, E` | `4B` | 1 | C <- E |
| | `LD C, H` | `4C` | 1 | C <- H |
| | `LD C, L` | `4D` | 1 | C <- L |
| | `LD C, (HL)` | `4E` | 1 | C <- (HL) |
| | `LD C, A` | `4F` | 1 | C <- A |
| | `LD D, B` | `50` | 1 | D <- B |
| | `LD D, C` | `51` | 1 | D <- C |
| | `LD D, D` | `52` | 1 | D <- D |
| | `LD D, E` | `53` | 1 | D <- E |
| | `LD D, H` | `54` | 1 | D <- H |
| | `LD D, L` | `55` | 1 | D <- L |
| | `LD D, (HL)` | `56` | 1 | D <- (HL) |
| | `LD D, A` | `57` | 1 | D <- A |
| | `LD E, B` | `58` | 1 | E <- B |
| | `LD E, C` | `59` | 1 | E <- C |
| | `LD E, D` | `5A` | 1 | E <- D |
| | `LD E, E` | `5B` | 1 | E <- E |
| | `LD E, H` | `5C` | 1 | E <- H |
| | `LD E, L` | `5D` | 1 | E <- L |
| | `LD E, (HL)` | `5E` | 1 | E <- (HL) |
| | `LD E, A` | `5F` | 1 | E <- A |
| | `LD H, B` | `60` | 1 | H <- B |
| | `LD H, C` | `61` | 1 | H <- C |
| | `LD H, D` | `62` | 1 | H <- D |
| | `LD H, E` | `63` | 1 | H <- E |
| | `LD H, H` | `64` | 1 | H <- H |
| | `LD H, L` | `65` | 1 | H <- L |
| | `LD H, (HL)` | `66` | 1 | H <- (HL) |
| | `LD H, A` | `67` | 1 | H <- A |
| | `LD L, B` | `68` | 1 | L <- B |
| | `LD L, C` | `69` | 1 | L <- C |
| | `LD L, D` | `6A` | 1 | L <- D |
| | `LD L, E` | `6B` | 1 | L <- E |
| | `LD L, H` | `6C` | 1 | L <- H |
| | `LD L, L` | `6D` | 1 | L <- L |
| | `LD L, (HL)` | `6E` | 1 | L <- (HL) |
| | `LD L, A` | `6F` | 1 | L <- A |
| | `LD (HL), B` | `70` | 1 | (HL) <- B |
| | `LD (HL), C` | `71` | 1 | (HL) <- C |
| | `LD (HL), D` | `72` | 1 | (HL) <- D |
| | `LD (HL), E` | `73` | 1 | (HL) <- E |
| | `LD (HL), H` | `74` | 1 | (HL) <- H |
| | `LD (HL), L` | `75` | 1 | (HL) <- L |
| | `LD (HL), A` | `77` | 1 | (HL) <- A |
| | `LD A, B` | `78` | 1 | A <- B |
| | `LD A, C` | `79` | 1 | A <- C |
| | `LD A, D` | `7A` | 1 | A <- D |
| | `LD A, E` | `7B` | 1 | A <- E |
| | `LD A, H` | `7C` | 1 | A <- H |
| | `LD A, L` | `7D` | 1 | A <- L |
| | `LD A, (HL)` | `7E` | 1 | A <- (HL) |
| | `LD A, A` | `7F` | 1 | A <- A |
| **8ビット算術 (レジスタ間/メモリ間接)** | `ADD A, B` | `80` | 1 | A <- A + B |
| | `ADD A, C` | `81` | 1 | A <- A + C |
| | `ADD A, D` | `82` | 1 | A <- A + D |
| | `ADD A, E` | `83` | 1 | A <- A + E |
| | `ADD A, H` | `84` | 1 | A <- A + H |
| | `ADD A, L` | `85` | 1 | A <- A + L |
| | `ADD A, (HL)` | `86` | 1 | A <- A + (HL) |
| | `ADD A, A` | `87` | 1 | A <- A + A |
| | `ADC A, B` | `88` | 1 | A <- A + B + C (キャリー込み) |
| | `ADC A, C` | `89` | 1 | A <- A + C + Cフラグ |
| | `ADC A, D` | `8A` | 1 | A <- A + D + Cフラグ |
| | `ADC A, E` | `8B` | 1 | A <- A + E + Cフラグ |
| | `ADC A, H` | `8C` | 1 | A <- A + H + Cフラグ |
| | `ADC A, L` | `8D` | 1 | A <- A + L + Cフラグ |
| | `ADC A, (HL)` | `8E` | 1 | A <- A + (HL) + Cフラグ |
| | `ADC A, A` | `8F` | 1 | A <- A + A + Cフラグ |
| | `SUB B` | `90` | 1 | A <- A - B |
| | `SUB C` | `91` | 1 | A <- A - C |
| | `SUB D` | `92` | 1 | A <- A - D |
| | `SUB E` | `93` | 1 | A <- A - E |
| | `SUB H` | `94` | 1 | A <- A - H |
| | `SUB L` | `95` | 1 | A <- A - L |
| | `SUB (HL)` | `96` | 1 | A <- A - (HL) |
| | `SUB A` | `97` | 1 | A <- A - A |
| | `SBC A, B` | `98` | 1 | A <- A - B - Cフラグ |
| | `SBC A, C` | `99` | 1 | A <- A - C - Cフラグ |
| | `SBC A, D` | `9A` | 1 | A <- A - D - Cフラグ |
| | `SBC A, E` | `9B` | 1 | A <- A - E - Cフラグ |
| | `SBC A, H` | `9C` | 1 | A <- A - H - Cフラグ |
| | `SBC A, L` | `9D` | 1 | A <- A - L - Cフラグ |
| | `SBC A, (HL)` | `9E` | 1 | A <- A - (HL) - Cフラグ |
| | `SBC A, A` | `9F` | 1 | A <- A - A - Cフラグ |
| | `AND B` | `A0` | 1 | A <- A AND B |
| | `AND C` | `A1` | 1 | A <- A AND C |
| | `AND D` | `A2` | 1 | A <- A AND D |
| | `AND E` | `A3` | 1 | A <- A AND E |
| | `AND H` | `A4` | 1 | A <- A AND H |
| | `AND L` | `A5` | 1 | A <- A AND L |
| | `AND (HL)` | `A6` | 1 | A <- A AND (HL) |
| | `AND A` | `A7` | 1 | A <- A AND A |
| | `XOR B` | `A8` | 1 | A <- A XOR B |
| | `XOR C` | `A9` | 1 | A <- A XOR C |
| | `XOR D` | `AA` | 1 | A <- A XOR D |
| | `XOR E` | `AB` | 1 | A <- A XOR E |
| | `XOR H` | `AC` | 1 | A <- A XOR H |
| | `XOR L` | `AD` | 1 | A <- A XOR L |
| | `XOR (HL)` | `AE` | 1 | A <- A XOR (HL) |
| | `XOR A` | `AF` | 1 | A <- A XOR A |
| | `OR B` | `B0` | 1 | A <- A OR B |
| | `OR C` | `B1` | 1 | A <- A OR C |
| | `OR D` | `B2` | 1 | A <- A OR D |
| | `OR E` | `B3` | 1 | A <- A OR E |
| | `OR H` | `B4` | 1 | A <- A OR H |
| | `OR L` | `B5` | 1 | A <- A OR L |
| | `OR (HL)` | `B6` | 1 | A <- A OR (HL) |
| | `OR A` | `B7` | 1 | A <- A OR A |
| | `CP B` | `B8` | 1 | A と B を比較（結果はフラグのみ） |
| | `CP C` | `B9` | 1 | A と C を比較（結果はフラグのみ） |
| | `CP D` | `BA` | 1 | A と D を比較（結果はフラグのみ） |
| | `CP E` | `BB` | 1 | A と E を比較（結果はフラグのみ） |
| | `CP H` | `BC` | 1 | A と H を比較（結果はフラグのみ） |
| | `CP L` | `BD` | 1 | A と L を比較（結果はフラグのみ） |
| | `CP (HL)` | `BE` | 1 | A と (HL) を比較（結果はフラグのみ） |
| | `CP A` | `BF` | 1 | A と A を比較（結果はフラグのみ） |
| **8ビットロード (直接アドレス)** | `LD (nn),A` | `32 nn nn` | 3 | (nn) <- A |
| | `LD A,(nn)` | `3A nn nn` | 3 | A <- (nn) |
| **16ビットロード/スタック/演算** | `LD BC,nn` | `01 nn nn` | 3 | BC <- nn |
| | `LD DE,nn` | `11 nn nn` | 3 | DE <- nn |
| | `LD HL,nn` | `21 nn nn` | 3 | HL <- nn |
| | `LD SP,nn` | `31 nn nn` | 3 | SP <- nn |
| | `LD (nn),BC` | `ED 43 nn nn` | 4 | (nn) <- BC |
| | `LD (nn),DE` | `ED 53 nn nn` | 4 | (nn) <- DE |
| | `LD (nn),HL` | `22 nn nn` | 3 | (nn) <- HL |
| | `LD (nn),SP` | `ED 73 nn nn` | 4 | (nn) <- SP |
| | `LD BC,(nn)` | `ED 4B nn nn` | 4 | BC <- (nn) |
| | `LD DE,(nn)` | `ED 5B nn nn` | 4 | DE <- (nn) |
| | `LD HL,(nn)` | `2A nn nn` | 3 | HL <- (nn) |
| | `LD SP,(nn)` | `ED 7B nn nn` | 4 | SP <- (nn) |
| | `LD SP,HL` | `F9` | 1 | SP <- HL |
| | `PUSH BC`, `PUSH DE`, `PUSH HL`, `PUSH AF` | `C5`, `D5`, `E5`, `F5` | 1 | スタックへプッシュ |
| | `POP BC`, `POP DE`, `POP HL`, `POP AF` | `C1`, `D1`, `E1`, `F1` | 1 | スタックからポップ |
| | `ADD HL,BC`, `ADD HL,DE`, `ADD HL,HL`, `ADD HL,SP` | `09`, `19`, `29`, `39` | 1 | HL <- HL + rr |
| | `ADC HL,BC`, `ADC HL,DE`, `ADC HL,HL`, `ADC HL,SP` | `ED 4A`, `ED 5A`, `ED 6A`, `ED 7A` | 2 | キャリー込み加算 |
| | `SBC HL,BC`, `SBC HL,DE`, `SBC HL,HL`, `SBC HL,SP` | `ED 42`, `ED 52`, `ED 62`, `ED 72` | 2 | キャリー込み減算 |
| | `INC BC`, `DEC BC` | `03`, `0B` | 1 | 16ビットインクリメント/デクリメント |
| | `INC DE`, `DEC DE` | `13`, `1B` | 1 | 〃 |
| | `INC HL`, `DEC HL` | `23`, `2B` | 1 | 〃 |
| | `INC SP`, `DEC SP` | `33`, `3B` | 1 | 〃 |
| **分岐命令** | `JP nn` | `C3 nn nn` | 3 | 無条件ジャンプ |
| | `JP NZ,nn`, `JP Z,nn` | `C2 nn nn`, `CA nn nn` | 3 | Zフラグによる条件ジャンプ |
| | `JP NC,nn`, `JP C,nn` | `D2 nn nn`, `DA nn nn` | 3 | Cフラグによる条件ジャンプ |
| | `JP PO,nn`, `JP PE,nn` | `E2 nn nn`, `EA nn nn` | 3 | P/Vフラグによる条件ジャンプ |
| | `JP P,nn`, `JP M,nn` | `F2 nn nn`, `FA nn nn` | 3 | Sフラグによる条件ジャンプ |
| | `JP (HL)` | `E9` | 1 | HLが指すアドレスへジャンプ |
| | `CALL nn` | `CD nn nn` | 3 | サブルーチン呼び出し |
| | `CALL NZ,nn` ... `CALL M,nn` | `C4 nn nn` ... `FC nn nn` | 3 | 条件付きコール |
| | `RET` | `C9` | 1 | サブルーチン復帰 |
| | `RET NZ` ... `RET M` | `C0` ... `F8` | 1 | 条件付きリターン |
| | `RST 00H` ... `RST 38H` | `C7` ... `FF` | 1 | リスタートベクタ呼び出し |
| **CB: ビット操作** | `RLC B` | `CB 00` | 2 | `RLC C` |
| | `RLC C` | `CB 01` | 2 | ... (以下、`RLC/RRC/RL/RR/SLA/SRA/SRL` の全レジスタ/メモリ組み合わせが続く) |
| | `BIT 0, B` | `CB 40` | 2 | `BIT 0, C` |
| | `BIT 0, C` | `CB 41` | 2 | ... (以下、`BIT n, r` の全組み合わせが続く) |
| | `RES 0, B` | `CB 80` | 2 | `RES 0, C` |
| | `RES 0, C` | `CB 81` | 2 | ... (以下、`RES n, r` の全組み合わせが続く) |
| | `SET 0, B` | `CB C0` | 2 | `SET 0, C` |
| | `SET 0, C` | `CB C1` | 2 | ... (以下、`SET n, r` の全組み合わせが続く) |
| **ED: ブロック転送/I/O** | `LDI`, `LDD`, `LDIR`, `LDDR` | `ED A0`, `ED A8`, `ED B0`, `ED B8` | 2 | ブロック転送 |
| | `CPI`, `CPD`, `CPIR`, `CPDR` | `ED A1`, `ED A9`, `ED B1`, `ED B9` | 2 | ブロック比較 |
| | `IN B,(C)`, `OUT (C),B` | `ED 40`, `ED 41` | 2 | ポートI/O |
| | `INI`, `IND`, `INIR`, `INDR` | `ED A2`, `ED AA`, `ED B2`, `ED BA` | 2 | ブロック入力 |
| | `OUTI`, `OUTD`, `OUTIR`, `OUTDR` | `ED A3`, `ED AB`, `ED B3`, `ED BB` | 2 | ブロック出力 |
| | `NEG` | `ED 44` | 2 | A <- 0 - A （2の補数） |
| | `RETN`, `RETI` | `ED 45`, `ED 4D` | 2 | 割り込みからの復帰 |
| | `IM 0`, `IM 1`, `IM 2` | `ED 46`, `ED 56`, `ED 5E` | 2 | 割り込みモード設定 |
| | `LD I, A`, `LD R, A` | `ED 47`, `ED 4F` | 2 | I/Rレジスタへのロード |
| | `LD A, I`, `LD A, R` | `ED 57`, `ED 5F` | 2 | I/Rレジスタからの読み出し |