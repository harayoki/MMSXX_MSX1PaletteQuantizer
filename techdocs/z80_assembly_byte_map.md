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
| **8ビットロード (即値)** | `LD B,n` | `06 n` | 2 | B $\leftarrow$ n |
| | `LD C,n` | `0E n` | 2 | C $\leftarrow$ n |
| | `LD D,n` | `16 n` | 2 | D $\leftarrow$ n |
| | `LD E,n` | `1E n` | 2 | E $\leftarrow$ n |
| | `LD H,n` | `26 n` | 2 | H $\leftarrow$ n |
| | `LD L,n` | `2E n` | 2 | L $\leftarrow$ n |
| | `LD (HL),n` | `36 n` | 2 | (HL) $\leftarrow$ n |
| | `LD A,n` | `3E n` | 2 | A $\leftarrow$ n |
| **8ビットロード (BC/DE間接)** | `LD (BC),A` | `02` | 1 | (BC) $\leftarrow$ A |
| | `LD A,(BC)` | `0A` | 1 | A $\leftarrow$ (BC) |
| | `LD (DE),A` | `12` | 1 | (DE) $\leftarrow$ A |
| | `LD A,(DE)` | `1A` | 1 | A $\leftarrow$ (DE) |
| **8ビットロード (レジスタ間 $LD r, r'$ )** | `LD B, B` | `40` | 1 | `LD B, C` |
| | `LD B, C` | `41` | 1 | `LD B, D` |
| | `LD B, D` | `42` | 1 | `LD B, E` |
| | `LD B, E` | `43` | 1 | `LD B, H` |
| | `LD B, H` | `44` | 1 | `LD B, L` |
| | `LD B, L` | `45` | 1 | `LD B, (HL)` |
| | `LD B, (HL)` | `46` | 1 | `LD B, A` |
| | `LD B, A` | `47` | 1 | `LD C, B` |
| | `LD C, B` | `48` | 1 | `LD C, C` |
| | `LD C, C` | `49` | 1 | `LD C, D` |
| | `LD C, D` | `4A` | 1 | `LD C, E` |
| | `LD C, E` | `4B` | 1 | `LD C, H` |
| | `LD C, H` | `4C` | 1 | `LD C, L` |
| | `LD C, L` | `4D` | 1 | `LD C, (HL)` |
| | `LD C, (HL)` | `4E` | 1 | `LD C, A` |
| | `LD C, A` | `4F` | 1 | `LD D, B` |
| | `LD D, B` | `50` | 1 | `LD D, C` |
| | `LD D, C` | `51` | 1 | `LD D, D` |
| | `LD D, D` | `52` | 1 | `LD D, E` |
| | `LD D, E` | `53` | 1 | `LD D, H` |
| | `LD D, H` | `54` | 1 | `LD D, L` |
| | `LD D, L` | `55` | 1 | `LD D, (HL)` |
| | `LD D, (HL)` | `56` | 1 | `LD D, A` |
| | `LD D, A` | `57` | 1 | `LD E, B` |
| | `LD E, B` | `58` | 1 | `LD E, C` |
| | `LD E, C` | `59` | 1 | `LD E, D` |
| | `LD E, D` | `5A` | 1 | `LD E, E` |
| | `LD E, E` | `5B` | 1 | `LD E, H` |
| | `LD E, H` | `5C` | 1 | `LD E, L` |
| | `LD E, L` | `5D` | 1 | `LD E, (HL)` |
| | `LD E, (HL)` | `5E` | 1 | `LD E, A` |
| | `LD E, A` | `5F` | 1 | `LD H, B` |
| | `LD H, B` | `60` | 1 | `LD H, C` |
| | `LD H, C` | `61` | 1 | `LD H, D` |
| | `LD H, D` | `62` | 1 | `LD H, E` |
| | `LD H, E` | `63` | 1 | `LD H, H` |
| | `LD H, H` | `64` | 1 | `LD H, L` |
| | `LD H, L` | `65` | 1 | `LD H, (HL)` |
| | `LD H, (HL)` | `66` | 1 | `LD H, A` |
| | `LD H, A` | `67` | 1 | `LD L, B` |
| | `LD L, B` | `68` | 1 | `LD L, C` |
| | `LD L, C` | `69` | 1 | `LD L, D` |
| | `LD L, D` | `6A` | 1 | `LD L, E` |
| | `LD L, E` | `6B` | 1 | `LD L, H` |
| | `LD L, H` | `6C` | 1 | `LD L, L` |
| | `LD L, L` | `6D` | 1 | `LD L, (HL)` |
| | `LD L, (HL)` | `6E` | 1 | `LD L, A` |
| | `LD L, A` | `6F` | 1 | `LD (HL), B` |
| | `LD (HL), B` | `70` | 1 | `LD (HL), C` |
| | `LD (HL), C` | `71` | 1 | `LD (HL), D` |
| | `LD (HL), D` | `72` | 1 | `LD (HL), E` |
| | `LD (HL), E` | `73` | 1 | `LD (HL), H` |
| | `LD (HL), H` | `74` | 1 | `LD (HL), L` |
| | `LD (HL), L` | `75` | 1 | `LD (HL), A` |
| | `LD (HL), A` | `77` | 1 | `LD A, B` |
| | `LD A, B` | `78` | 1 | `LD A, C` |
| | `LD A, C` | `79` | 1 | `LD A, D` |
| | `LD A, D` | `7A` | 1 | `LD A, E` |
| | `LD A, E` | `7B` | 1 | `LD A, H` |
| | `LD A, H` | `7C` | 1 | `LD A, L` |
| | `LD A, L` | `7D` | 1 | `LD A, (HL)` |
| | `LD A, (HL)` | `7E` | 1 | `LD A, A` |
| | `LD A, A` | `7F` | 1 | A $\leftarrow$ A |
| **8ビット算術 (レジスタ間/メモリ間接)** | `ADD A, B` | `80` | 1 | `ADD A, C` |
| | `ADD A, C` | `81` | 1 | `ADD A, D` |
| | `ADD A, D` | `82` | 1 | `ADD A, E` |
| | `ADD A, E` | `83` | 1 | `ADD A, H` |
| | `ADD A, H` | `84` | 1 | `ADD A, L` |
| | `ADD A, L` | `85` | 1 | `ADD A, (HL)` |
| | `ADD A, (HL)` | `86` | 1 | `ADD A, A` |
| | `ADD A, A` | `87` | 1 | `ADC A, B` |
| | `ADC A, B` | `88` | 1 | `ADC A, C` |
| | `ADC A, C` | `89` | 1 | `ADC A, D` |
| | `ADC A, D` | `8A` | 1 | `ADC A, E` |
| | `ADC A, E` | `8B` | 1 | `ADC A, H` |
| | `ADC A, H` | `8C` | 1 | `ADC A, L` |
| | `ADC A, L` | `8D` | 1 | `ADC A, (HL)` |
| | `ADC A, (HL)` | `8E` | 1 | `ADC A, A` |
| | `ADC A, A` | `8F` | 1 | `SUB B` |
| | `SUB B` | `90` | 1 | `SUB C` |
| | `SUB C` | `91` | 1 | `SUB D` |
| | `SUB D` | `92` | 1 | `SUB E` |
| | `SUB E` | `93` | 1 | `SUB H` |
| | `SUB H` | `94` | 1 | `SUB L` |
| | `SUB L` | `95` | 1 | `SUB (HL)` |
| | `SUB (HL)` | `96` | 1 | `SUB A` |
| | `SUB A` | `97` | 1 | `SBC A, B` |
| | `SBC A, B` | `98` | 1 | `SBC A, C` |
| | `SBC A, C` | `99` | 1 | `SBC A, D` |
| | `SBC A, D` | `9A` | 1 | `SBC A, E` |
| | `SBC A, E` | `9B` | 1 | `SBC A, H` |
| | `SBC A, H` | `9C` | 1 | `SBC A, L` |
| | `SBC A, L` | `9D` | 1 | `SBC A, (HL)` |
| | `SBC A, (HL)` | `9E` | 1 | `SBC A, A` |
| | `SBC A, A` | `9F` | 1 | `AND B` |
| | `AND B` | `A0` | 1 | `AND C` |
| | `AND C` | `A1` | 1 | `AND D` |
| | `AND D` | `A2` | 1 | `AND E` |
| | `AND E` | `A3` | 1 | `AND H` |
| | `AND H` | `A4` | 1 | `AND L` |
| | `AND L` | `A5` | 1 | `AND (HL)` |
| | `AND (HL)` | `A6` | 1 | `AND A` |
| | `AND A` | `A7` | 1 | `XOR B` |
| | `XOR B` | `A8` | 1 | `XOR C` |
| | `XOR C` | `A9` | 1 | `XOR D` |
| | `XOR D` | `AA` | 1 | `XOR E` |
| | `XOR E` | `AB` | 1 | `XOR H` |
| | `XOR H` | `AC` | 1 | `XOR L` |
| | `XOR L` | `AD` | 1 | `XOR (HL)` |
| | `XOR (HL)` | `AE` | 1 | `XOR A` |
| | `XOR A` | `AF` | 1 | `OR B` |
| | `OR B` | `B0` | 1 | `OR C` |
| | `OR C` | `B1` | 1 | `OR D` |
| | `OR D` | `B2` | 1 | `OR E` |
| | `OR E` | `B3` | 1 | `OR H` |
| | `OR H` | `B4` | 1 | `OR L` |
| | `OR L` | `B5` | 1 | `OR (HL)` |
| | `OR (HL)` | `B6` | 1 | `OR A` |
| | `OR A` | `B7` | 1 | `CP B` |
| | `CP B` | `B8` | 1 | `CP C` |
| | `CP C` | `B9` | 1 | `CP D` |
| | `CP D` | `BA` | 1 | `CP E` |
| | `CP E` | `BB` | 1 | `CP H` |
| | `CP H` | `BC` | 1 | `CP L` |
| | `CP L` | `BD` | 1 | `CP (HL)` |
| | `CP (HL)` | `BE` | 1 | `CP A` |
| | `CP A` | `BF` | 1 | `LD (nn), A` |
| **8ビットロード (直接アドレス)** | `LD (nn),A` | `32 nn nn` | 3 | (nn) $\leftarrow$ A |
| | `LD A,(nn)` | `3A nn nn` | 3 | A $\leftarrow$ (nn) |
| **16ビットロード/スタック/演算** | `LD BC,nn` | `01 nn nn` | 3 | BC $\leftarrow$ nn |
| | `LD DE,nn` | `11 nn nn` | 3 | DE $\leftarrow$ nn |
| | `LD HL,nn` | `21 nn nn` | 3 | HL $\leftarrow$ nn |
| | `LD SP,nn` | `31 nn nn` | 3 | SP $\leftarrow$ nn |
| | `LD (nn),BC` | `ED 43 nn nn` | 4 | (nn) $\leftarrow$ BC |
| | `LD (nn),DE` | `ED 53 nn nn` | 4 | (nn) $\leftarrow$ DE |
| | `LD (nn),HL` | `22 nn nn` | 3 | (nn) $\leftarrow$ HL |
| | `LD (nn),SP` | `ED 73 nn nn` | 4 | (nn) $\leftarrow$ SP |
| | `LD BC,(nn)` | `ED 4B nn nn` | 4 | BC $\leftarrow$ (nn) |
| | `LD DE,(nn)` | `ED 5B nn nn` | 4 | DE $\leftarrow$ (nn) |
| | `LD HL,(nn)` | `2A nn nn` | 3 | HL $\leftarrow$ (nn) |
| | `LD SP,(nn)` | `ED 7B nn nn` | 4 | SP $\leftarrow$ (nn) |
| | `LD SP,HL` | `F9` | 1 | SP $\leftarrow$ HL |
| | `PUSH BC`, `PUSH DE`, `PUSH HL`, `PUSH AF` | `C5`, `D5`, `E5`, `F5` | 1 | スタックへプッシュ |
| | `POP BC`, `POP DE`, `POP HL`, `POP AF` | `C1`, `D1`, `E1`, `F1` | 1 | スタックからポップ |
| | `ADD HL,BC`, `ADD HL,DE`, `ADD HL,HL`, `ADD HL,SP` | `09`, `19`, `29`, `39` | 1 | HL $\leftarrow$ HL + rr |
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
| | `NEG` | `ED 44` | 2 | A $\leftarrow$ 0 - A （2の補数） |
| | `RETN`, `RETI` | `ED 45`, `ED 4D` | 2 | 割り込みからの復帰 |
| | `IM 0`, `IM 1`, `IM 2` | `ED 46`, `ED 56`, `ED 5E` | 2 | 割り込みモード設定 |
| | `LD I, A`, `LD R, A` | `ED 47`, `ED 4F` | 2 | I/Rレジスタへのロード |
| | `LD A, I`, `LD A, R` | `ED 57`, `ED 5F` | 2 | I/Rレジスタからの読み出し |