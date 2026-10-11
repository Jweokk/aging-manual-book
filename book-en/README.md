# English edition — 对应表与规则（骨架）

英文版**先建骨架**：文件名在这里一次定死，`llms.txt` 与闸门脚本才有一致的目标可引。
中文版是主版，先上线；英文按篇分批推进（第 1 批：序 + 第 0 章 + 免责声明 + 篇一、篇二；
第 2 批：篇三、篇四；第 3 批：篇五 + 结语 + 附录）。

站点：**https://aging.fly2ai.top/en/**，与中文站同域挂在 `/en/` 下（GitHub Pages 一个仓库一个自定义域名，
子路径比再开一套仓库+域名省事，也不动已有的中文链接）。站点结构由 `tools/gen_mkdocs_en.py` 从本表的
对应表生成，**只有已经译好的单元才进导航**；没译的单元不出现，读者不会点到空页。

## 中英文件对应表

| 中文（book/） | 英文（book-en/） |
|---|---|
| `00-第0章-这份说明书怎么用.md` | `00-how-to-use-this-book.md` |
| `序-老年人就是我们未来的样子.md` | `01-foreword-our-parents-are-our-future.md` |
| `03-关于这份资料与免责声明.md` | `02-about-this-book-and-disclaimer.md` |
| `01-第1章-变老不是某一天发生的.md` | `03-ch1-growing-old-does-not-happen-in-one-day.md` |
| `02-第2章-骨本与肌肉本.md` | `04-ch2-bone-and-muscle-capital.md` |
| `03-第3章-脑本与感官本.md` | `05-ch3-brain-and-senses-capital.md` |
| `04-第4章-钱本与关系本.md` | `06-ch4-money-and-relationships-capital.md` |
| `05-第5章-跌倒是晚年的第一道分水岭.md` | `07-ch5-falls-the-first-turning-point.md` |
| `06-第6章-药不是吃得越多越好.md` | `08-ch6-more-medicine-is-not-better.md` |
| `07-第7章-吃不下咽不下噎住.md` | `09-ch7-cant-eat-cant-swallow-choking.md` |
| `08-第8章-三条就医红线与第一小时.md` | `10-ch8-three-red-lines-and-the-first-hour.md` |
| `09-第9章-记不住-从健忘到痴呆有多远.md` | `11-ch9-forgetting-how-far-from-dementia.md` |
| `10-第10章-尿便与体面.md` | `12-ch10-incontinence-toileting-and-dignity.md` |
| `11-第11章-睡不着疼心里没劲孤独.md` | `13-ch11-sleepless-pain-apathy-loneliness.md` |
| `12-第12章-每天怎么吃.md` | `14-ch12-what-to-eat-every-day.md` |
| `13-第13章-每天怎么动.md` | `15-ch13-how-to-move-every-day.md` |
| `14-第14章-疫苗筛查和体检单.md` | `16-ch14-vaccines-screening-and-checkup.md` |
| `15-第15章-住哪儿和谁一起老.md` | `17-ch15-where-to-live-and-with-whom.md` |
| `16-第16章-钱从哪来制度怎么替你付账.md` | `18-ch16-where-the-money-comes-from.md` |
| `17-第17章-人从哪来与给照护者的部分.md` | `19-ch17-where-the-helpers-come-from.md` |
| `18-第18章-手机与骗局把事办成别被套走.md` | `20-ch18-phones-and-scams.md` |
| `19-第19章-权限设置趁清醒把权限交出去.md` | `21-ch19-handing-over-authority.md` |
| `20-第20章-怎么开口.md` | `22-ch20-how-to-start-the-conversation.md` |
| `21-第21章-走下坡之前.md` | `23-ch21-before-the-slope-starts.md` |
| `22-第22章-谢幕之后.md` | `24-ch22-after-the-curtain-falls.md` |
| `30-结语.md` | `30-afterword-when-the-manual-is-dog-eared.md` |
| `41-附录A.md` | `41-appendix-a-national-entitlements-ledger.md` |
| `42-附录B-症状速查表.md` | `42-appendix-b-symptom-lookup.md` |
| `43-附录C-恐惧速查表.md` | `43-appendix-c-fear-lookup.md` |
| `44-附录D-叫120判断表.md` | `44-appendix-d-when-to-call-120.md` |
| `45-附录E-话术卡.md` | `45-appendix-e-phrase-cards.md` |
| `46-附录F-延伸阅读.md` | `46-appendix-f-further-reading.md` |

## 翻译规则

1. **结构与编号一一对应**：七栏栏目名逐条对应（要花多少 → What it costs｜简单说 → In short｜可以怎么做 → What you can do｜来源 → Where this comes from｜特别提醒 → Who this is for｜换回来的 → What you get back｜在中国怎么落地 → How this works in China）；栏目数量与顺序不得改动。
2. **数字、日期、文号、URL 逐字照抄**：`3.0854 亿`、`79.25 岁`、`民发〔2025〕37 号`、链接一律原样，不得四舍五入、不得"简化"。
3. **证据分档 1:1 映射**：A/B/C 三档不增不减（见 `../assets/glossary-en.md`）。
4. **制度与钱的部分不是直译，是改写**：面向英文读者写明"这是中国大陆的制度"＋与读者所在制度的差异提示（例如长护险 vs 美国的 LTC insurance、医保 vs Medicare、意定监护 vs power of attorney）。**不评价哪种制度更好。**
5. **医学与照护部分直译**，但来源优先引英文原始文献（WHO／Cochrane／NICE／AGS），中文文献在英文版里给英文译名 + 原题。
6. **不出现本站域名**（`fly2ai.top`）与中文社交平台名；需要指向附录时用"see Appendix C"。
7. **正文干净**：不加数字上标、不解释编辑记号；〔待核〕在英文版里写作 `[unverified]`，〔转引〕写作 `[second-hand]`。

## 验收（父代理自己做，第一批就做）

- 文件存在，且命名与上表、`llms.txt` 的 EN 链接**逐个吻合**；
- `## ` 级标题数、栏目数、表格行数与中文版对齐；
- URL 集合相等（增删都算错）；分档计数 1:1；
- `grep -c fly2ai` = 0；`<sup>` = 0。
