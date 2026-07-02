#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""律師國考考古題解析器 ── 執行此檔案以產生 js/questions_data.js"""
import re, json
from pathlib import Path
from collections import defaultdict

# ── 題目檔科目對應（4大科） ────────────────────────────────
def exam_subject(filename):
    if '刑法刑訴' in filename: return 'criminal'
    if '憲法行政' in filename: return 'constitutional'
    if '民法民訴' in filename: return 'civil'
    if '商法'     in filename: return 'commercial'
    return 'other'

def get_year(filename):
    m = re.search(r'_(\d+)年_', filename)
    return int(m.group(1)) if m else 0

# ── 主題 → 單科 mapping ─────────────────────────────────────
TOPIC_TO_LAW = {
    # 刑法（12）
    'crim_罪刑法定':'刑法','crim_構成要件':'刑法','crim_違法性':'刑法',
    'crim_罪責':'刑法','crim_未遂':'刑法','crim_共犯':'刑法',
    'crim_競合刑罰':'刑法','crim_生命身體':'刑法','crim_性侵自由':'刑法',
    'crim_財產':'刑法','crim_公共危險':'刑法','crim_職務偽造':'刑法',
    # 刑事訴訟法（7）
    'cpc_基本':'刑事訴訟法','cpc_強制':'刑事訴訟法','cpc_偵查':'刑事訴訟法',
    'cpc_證據':'刑事訴訟法','cpc_審判':'刑事訴訟法',
    'cpc_救濟':'刑事訴訟法','cpc_特殊':'刑事訴訟法',
    # 法律倫理（3）
    'ethics_法官':'法律倫理','ethics_檢察官':'法律倫理','ethics_律師':'法律倫理',
    # 憲法（5）
    'const_原則':'憲法','const_基本權':'憲法','const_違憲審查':'憲法',
    'const_五院':'憲法','const_修憲':'憲法',
    # 行政法（7）
    'admin_原則':'行政法','admin_組織':'行政法','admin_行為':'行政法',
    'admin_罰':'行政法','admin_訴願':'行政法','admin_行政訴訟':'行政法','admin_地方':'行政法',
    # 國際公法（2）
    'intl_公法_法源':'國際公法','intl_公法_主體':'國際公法',
    # 國際私法（3）
    'intl_私法_總論':'國際私法','intl_私法_各論':'國際私法','intl_私法_程序':'國際私法',
    # 民法（10）
    'civil_總則':'民法','civil_債總':'民法','civil_買賣租賃':'民法',
    'civil_其他債各':'民法','civil_侵權不當':'民法',
    'civil_物權_所有':'民法','civil_物權_擔保':'民法',
    'civil_婚姻':'民法','civil_親子':'民法','civil_繼承':'民法',
    # 民事訴訟法（7）
    'civ_proc_管轄':'民事訴訟法','civ_proc_當事人':'民事訴訟法',
    'civ_proc_程序':'民事訴訟法','civ_proc_證據':'民事訴訟法',
    'civ_proc_上訴':'民事訴訟法','civ_proc_保全':'民事訴訟法',
    'civ_proc_家事':'民事訴訟法',
    # 公司法（5）
    'corp_通則':'公司法','corp_股份_組織':'公司法','corp_股份_資本':'公司法',
    'corp_股份_重組':'公司法','corp_關係企業':'公司法',
    # 票據法（4）
    'bill_總論':'票據法','bill_匯票':'票據法','bill_本票':'票據法','bill_支票':'票據法',
    # 海商法（1）
    'sea_海商':'海商法',
    # 保險法（4）
    'ins_總則':'保險法','ins_契約':'保險法','ins_財產':'保險法','ins_人身':'保險法',
    # 強制執行法（4）
    'exec_總則':'強制執行法','exec_金錢':'強制執行法',
    'exec_非金錢':'強制執行法','exec_保全':'強制執行法',
    # 證券交易法（3）
    'sec_發行':'證券交易法','sec_不法':'證券交易法','sec_監理':'證券交易法',
    # 法學英文（1）
    'eng_英文':'法學英文',
}

# ── 單科排序與分組 ─────────────────────────────────────────
LAW_SUBJECTS = [
    {'id':'刑法',       'group':'綜合法學一'},
    {'id':'刑事訴訟法', 'group':'綜合法學一'},
    {'id':'法律倫理',   'group':'綜合法學一'},
    {'id':'憲法',       'group':'綜合法學一'},
    {'id':'行政法',     'group':'綜合法學一'},
    {'id':'國際公法',   'group':'綜合法學一'},
    {'id':'國際私法',   'group':'綜合法學一'},
    {'id':'民法',       'group':'綜合法學二'},
    {'id':'民事訴訟法', 'group':'綜合法學二'},
    {'id':'公司法',     'group':'綜合法學二'},
    {'id':'票據法',     'group':'綜合法學二'},
    {'id':'海商法',     'group':'綜合法學二'},
    {'id':'保險法',     'group':'綜合法學二'},
    {'id':'強制執行法', 'group':'綜合法學二'},
    {'id':'證券交易法', 'group':'綜合法學二'},
    {'id':'法學英文',   'group':'綜合法學二'},
]

# ── 主題定義（含重要度） ────────────────────────────────────
TOPICS = {
    # ════ 刑法（12，不變）════
    'crim_罪刑法定':  dict(name='刑法總則｜罪刑法定原則', sf='criminal', kw=['罪刑法定','明確性','不溯及既往','類推','習慣法','構成要件明確','空白刑法','行政法令','授權明確','刑罰法定','溯及既往','刑法第1條'], imp=5),
    'crim_構成要件':  dict(name='刑法總則｜構成要件與客觀歸責', sf='criminal', kw=['構成要件','客觀歸責','因果關係','不作為','作為義務','保證人','相當因果','條件理論','結果','行為犯','舉動犯','間接客體','不純正不作為'], imp=5),
    'crim_違法性':    dict(name='刑法總則｜違法性（阻卻違法）', sf='criminal', kw=['正當防衛','緊急避難','阻卻違法','假想防衛','防衛過當','被害人承諾','推測承諾','超法規阻卻','業務上正當行為','誤想防衛','容許性錯誤'], imp=5),
    'crim_罪責':      dict(name='刑法總則｜罪責（故意過失錯誤）', sf='criminal', kw=['故意','過失','錯誤論','責任能力','精神障礙','期待可能性','禁止錯誤','原因自由行為','識別能力','告訴乃論','業務過失','抽象事實錯誤','具體事實錯誤','無責任能力'], imp=5),
    'crim_未遂':      dict(name='刑法總則｜未遂犯', sf='criminal', kw=['未遂','既遂','障礙未遂','中止未遂','不能未遂','著手','中止犯','陷阱','不能犯','危險犯'], imp=4),
    'crim_共犯':      dict(name='刑法總則｜共犯', sf='criminal', kw=['共同正犯','教唆犯','幫助犯','間接正犯','共犯','共謀','正犯','共謀正犯','身分犯','必要共犯','對向犯','聚眾犯'], imp=5),
    'crim_競合刑罰':  dict(name='刑法總則｜競合與刑罰沒收', sf='criminal', kw=['想像競合','實質競合','法規競合','沒收','追徵','競合','累犯','緩刑','假釋','易服勞役','褫奪公權','數罪','一行為','從一重','連續犯','牽連犯','追繳'], imp=4),
    'crim_生命身體':  dict(name='刑法各論｜生命身體法益', sf='criminal', kw=['殺人','傷害','重傷','遺棄','墮胎','義憤殺人','加工自殺','過失致死','殺直系','重傷害','傷害罪'], imp=4),
    'crim_性侵自由':  dict(name='刑法各論｜性侵妨害自由', sf='criminal', kw=['強制性交','性侵','妨害自由','強制','剝奪行動','性自主','猥褻','強暴脅迫','恐嚇','使不能抗拒','性騷擾'], imp=3),
    'crim_財產':      dict(name='刑法各論｜財產犯罪', sf='criminal', kw=['竊盜','強盜','詐欺','背信','侵占','毀損','搶奪','恐嚇取財','竊佔','財物','不法所有','洗錢','電信詐欺','財產上不法利益'], imp=4),
    'crim_公共危險':  dict(name='刑法各論｜公共危險', sf='criminal', kw=['放火','公共危險','酒駕','肇事逃逸','縱火','不能安全駕駛','爆炸','失火','燒燬','危害安全','投放毒物','重大事故'], imp=4),
    'crim_職務偽造':  dict(name='刑法各論｜職務偽造', sf='criminal', kw=['受賄','行賄','貪污','偽造','公務員','藏匿','偽造文書','偽證','電磁紀錄','準文書','公文書','私文書','業務文書','影本','盜用印章','圖利','職務犯罪','電腦犯罪','妨害電腦','湮滅','偽造貨幣','藏匿人犯','湮滅罪證'], imp=3),
    # ════ 刑事訴訟法（7，依考選部大綱拆分）════
    'cpc_基本':       dict(name='刑訴｜基本原理原則', sf='criminal', kw=['當事人主義','職權主義','彈劾主義','無罪推定','不自證己罪','審判公開','直接審理主義','言詞審理主義','集中審理','辯護人','強制辯護','輔佐人','管轄','迴避','期日','期間','文書送達','法院組織','刑事訴訟基本','訴訟原則'], imp=4),
    'cpc_強制':       dict(name='刑訴｜強制處分', sf='criminal', kw=['搜索','扣押','逮捕','羈押','票狀','傳喚','具保','拘提','通緝','限制出境','搜索票','緊急搜索','無票搜索','必要處分','限制出境出海','扣押物','羈押原因','停止羈押','聲請羈押','執行搜索'], imp=5),
    'cpc_偵查':       dict(name='刑訴｜偵查程序', sf='criminal', kw=['偵查','告訴','告發','自首','不起訴','緩起訴','偵查終結','偵查不公開','偵查機關','再議','交付審判','聲請停止偵查','移送','補充告訴','告訴代理人','告訴期間','告訴乃論','起訴裁量','聲請簡易'], imp=5),
    'cpc_證據':       dict(name='刑訴｜證據法則', sf='criminal', kw=['證據','自白','傳聞','非任意性','鑑定','勘驗','證據能力','補強','傳聞法則','直接審理','詰問','交互詰問','對質','書面陳述','排除法則','嚴格證明','自由證明','調查證據'], imp=5),
    'cpc_審判':       dict(name='刑訴｜審判程序', sf='criminal', kw=['起訴','公訴','準備程序','言詞辯論','辯護','蒞庭','強制辯護','第一審','自訴','審判期日','被告在庭','閱覽卷宗','程序終結','無罪判決','有罪判決'], imp=4),
    'cpc_救濟':       dict(name='刑訴｜救濟程序', sf='criminal', kw=['上訴','抗告','再審','非常上訴','第三審','發回','發交','確定判決','廢棄','違背法令','一事不再理','救濟程序','上訴期間','上訴理由','許可上訴'], imp=4),
    'cpc_特殊':       dict(name='刑訴｜特別程序', sf='criminal', kw=['簡易程序','協商','簡式審判','國民法官','刑事補償','少年刑事','附帶民事','沒收特別程序','通訊監察','妥速審判'], imp=3),
    # ════ 法律倫理（3，依考選部大綱：法官倫理/檢察官倫理/律師倫理）════
    'ethics_法官':    dict(name='法律倫理｜法官倫理', sf='criminal',
                         kw=['法官','審判','法官倫理','法官評鑑','法官懲戒','評鑑委員會','司法獨立','法院組織','審判獨立','在職法官','違反職務','職務迴避','審判行為','非職務','法官自律','兼職兼業','餽贈招待'], imp=3),
    'ethics_檢察官':  dict(name='法律倫理｜檢察官倫理', sf='criminal',
                         kw=['檢察官','偵查不公開','客觀義務','檢察一體','上命下從','不起訴','緩起訴','檢察署','偵查機關','起訴裁量','追訴','指揮偵查','偵查保密','檢察官倫理','檢察官懲戒','檢察評鑑'], imp=3),
    'ethics_律師':    dict(name='法律倫理｜律師倫理', sf='criminal',
                         kw=['律師','委任人','受任人','保密','忠實','利益衝突','律師法','律師懲戒','律師公會','廣告','酬金','律師倫理規範','業務守密','委任關係','律師費','迴避利益','律師與委任人','律師職業','律師責任','律師資格','法律扶助'], imp=3),
    # ════ 憲法（5，依考選部大綱：基本原則/基本權利/國家機關/憲法訴訟/修憲）════
    'const_原則':     dict(name='憲法｜憲法基本原則', sf='constitutional', kw=['民主原則','法治國原則','權力分立','社會國','制衡','民主正當性','法律明確性','憲法基本原則','立憲主義','最高規範','憲法位階','民主憲政','人性尊嚴','憲政秩序','民主自由'], imp=4),
    'const_基本權':   dict(name='憲法｜基本權保障', sf='constitutional', kw=['基本權','平等','人身自由','言論自由','財產權','工作權','集會','宗教','隱私','比例原則','人格權','名譽權','受教育','生存權','身體自由','遷徙自由','資訊隱私','基本人權','隱私權','個人資料','秘密通訊'], imp=5),
    'const_違憲審查': dict(name='憲法｜違憲審查與釋憲', sf='constitutional', kw=['違憲','大法官','釋字','比例原則','審查基準','憲法法庭','違憲宣告','裁判憲法訴願','暫時處分','合憲解釋','嚴格審查','中度審查','寬鬆審查','法規範憲法審查'], imp=5),
    'const_五院':     dict(name='憲法｜五院與統治機構', sf='constitutional',
                         kw=['立法院','行政院','司法院','總統','五院','副署','覆議','國情報告','考試院','監察院','三讀','程序委員會','閣揆','解散','倒閣','不信任案','緊急命令','戒嚴','行政院院長','審計長','糾彈','糾正','彈劾','罷免','閣揆任命','覆議案'], imp=4),
    'const_修憲':     dict(name='憲法｜修憲與基本國策', sf='constitutional',
                         kw=['修憲','憲法增修','基本國策','軍事','國軍','憲政機關','國家安全','增修條文','修憲程序','複決','兩岸關係','原住民','農漁'], imp=3),
    # ════ 行政法（7，admin_總論 拆為 admin_原則+admin_組織；admin_救濟 拆為 admin_訴願+admin_行政訴訟）════
    'admin_原則':     dict(name='行政法｜依法行政與基本原則', sf='constitutional',
                         kw=['依法行政','法律保留','法律優位','裁量','信賴保護','誠信原則','比例原則','行政自我拘束','授權明確','不當連結','裁量逾越','裁量怠惰','平等原則','期待保護','誠實信用','合理期待'], imp=5),
    'admin_組織':     dict(name='行政法｜行政組織', sf='constitutional',
                         kw=['行政機關','機關組織','行政院組織','中央行政','行政組織','組織基準法','獨立機關','委任','受託機關','行政委託','職權','主管機關','公法人','中央機關','行政程序','行政院院長'], imp=4),
    'admin_行為':     dict(name='行政法｜行政行為', sf='constitutional', kw=['行政處分','行政契約','行政命令','法規命令','行政指導','附款','行政規則','職權命令','授權命令','私法形式','事實行為','一般處分','多階段行政處分','裁量處分','行政行為','委任行政'], imp=5),
    'admin_罰':       dict(name='行政法｜行政罰', sf='constitutional', kw=['行政罰','裁罰','行政秩序罰','沒入','罰鍰','一行為不二罰','行政罰法','裁處期間','吊照','停業','連續罰'], imp=4),
    'admin_訴願':     dict(name='行政法｜訴願', sf='constitutional',
                         kw=['訴願','訴願決定','訴願機關','訴願法','訴願人','原處分機關','訴願期間','不受理訴願','先行訴願','訴願程序','撤回訴願','訴願有無理由','再訴願'], imp=5),
    'admin_行政訴訟': dict(name='行政法｜行政訴訟與國家賠償', sf='constitutional',
                         kw=['行政訴訟','撤銷訴訟','課予義務','確認訴訟','國家賠償','行政法院','徵收補償','損失補償','違法行政','行政爭訟','聲請停止執行','行政高等法院','最高行政法院'], imp=5),
    'admin_地方':     dict(name='行政法｜地方制度', sf='constitutional', kw=['地方制度','地方自治','直轄市','縣市','自治條例','地方自治法','自治事項','委辦事項','自治法規','鄉鎮','行政區','自治團體'], imp=3),
    # ════ 國際公法（2，由 intl_公法 拆分）════
    'intl_公法_法源': dict(name='國際公法｜法源與條約', sf='constitutional',
                         kw=['條約','習慣國際法','法源','批准','加入','條約法','條約保留','締結','條約解釋','維也納條約法','成文國際法','一般法律原則','法之確信'], imp=4),
    'intl_公法_主體': dict(name='國際公法｜主體、管轄與國際組織', sf='constitutional',
                         kw=['主權','領海','公海','領土','外交','外交豁免','外交保護','引渡','國際責任','承認','繼承','大陸礁層','國際組織','聯合國','國際刑事法院','人道法','難民','管轄豁免','專屬經濟區'], imp=4),
    # ════ 國際私法（2，由 intl_私法 拆分）════
    'intl_私法_總論': dict(name='國際私法｜準據法總論', sf='constitutional',
                         kw=['準據法','連結因素','反致','公序良俗','外國法','法律選擇','屬人法','屬地法','涉外民事法律適用法','識別','先決問題','當事人意思自主','最重要牽連','全程反致'], imp=4),
    'intl_私法_各論': dict(name='國際私法｜各種法律關係準據法', sf='constitutional',
                         kw=['本國法','住所地法','國籍','慣居地','涉外','婚姻','離婚','收養','繼承','物之所在地法','行為地法','法人','票據準據法','代理準據法','扶養','監護'], imp=4),
    'intl_私法_程序': dict(name='國際私法｜國際民事程序法', sf='constitutional',
                         kw=['國際管轄','外國裁判承認','外國判決','外國法院','應訴管轄','管轄合意','外國仲裁','承認執行','拒絕承認','承認外國仲裁','送達','調查取證','外國訴訟','涉外程序','國際訴訟競合'], imp=3),
    # ════ 民法（10，物權拆2+親屬拆2）════
    'civil_總則':     dict(name='民法｜總則', sf='civil', kw=['法律行為','意思表示','行為能力','代理','時效','條件','虛偽','通謀','消滅時效','請求權','限制行為能力','無行為能力','錯誤','詐欺','脅迫','撤銷','無效','有效成立','法人','社團','財團'], imp=5),
    'civil_債總':     dict(name='民法｜債法總論', sf='civil', kw=['債之發生','連帶','保證','抵銷','給付遲延','給付不能','不完全給付','情事變更','契約','清償','提存','代物清償','債務承擔','契約終止','解除','第三人利益契約','契約關係消滅','連帶債務','返還','讓與','債權讓與','通知','讓與通知','清算','履行輔助'], imp=5),
    'civil_買賣租賃': dict(name='民法｜買賣與租賃', sf='civil', kw=['買賣','租賃','出租','承租','瑕疵擔保','危險負擔','物之瑕疵','租期','終止租約','地上物','不動產買賣','一物數賣','標的物滅失'], imp=4),
    'civil_其他債各': dict(name='民法｜其他典型契約', sf='civil', kw=['消費借貸','使用借貸','委任','承攬','贈與','寄託','雇傭','居間','旅遊','合會','和解','定作人','承攬人','受任人','委任人'], imp=4),
    'civil_侵權不當': dict(name='民法｜侵權行為與不當得利', sf='civil', kw=['侵權行為','不當得利','無因管理','損害賠償','慰撫金','非財產上損害','共同侵權','僱主責任','商品製造人','動物所有人','工作物','受僱人','連帶損害賠償'], imp=5),
    'civil_物權_所有': dict(name='民法｜物權編－所有權與占有', sf='civil', kw=['所有權','不動產所有','動產所有','共有','分別共有','公同共有','共有物分割','添附','善意取得','先買權','占有','占有輔助人','占有改定','間接占有','物上請求權','回復請求','除去妨害','物權法定','不動產登記'], imp=5),
    'civil_物權_擔保': dict(name='民法｜物權編－用益物權與擔保物權', sf='civil', kw=['抵押權','地上權','農育權','不動產役權','質權','留置權','最高限額抵押','普通抵押','抵押物','抵押設定','擔保物權','用益物權','典權','動產質權','不動產抵押','抵押權實行','優先受償'], imp=5),
    'civil_婚姻':     dict(name='民法｜親屬編－婚姻', sf='civil', kw=['婚姻','結婚','離婚','夫妻','配偶','撤銷婚姻','婚約','法定夫妻財產制','約定夫妻財產制','剩餘財產分配','日常家務代理','裁判離婚','夫妻財產','婚前契約','通謀結婚','夫妻扶養'], imp=4),
    'civil_親子':     dict(name='民法｜親屬編－親子與監護扶養', sf='civil', kw=['父母','子女','親權','監護','扶養','認領','非婚生','準正','收養','撫育','扶養義務','法定代理','未成年子女','扶養請求','親子關係','生父','親等','監護人','輔助宣告'], imp=4),
    'civil_繼承':     dict(name='民法｜繼承法', sf='civil', kw=['繼承','遺囑','遺產','遺贈','應繼分','特留分','拋棄繼承','限定繼承','遺產管理人','繼承人','代位繼承','被繼承人','遺囑執行人','自書遺囑','公證遺囑'], imp=4),
    # ════ 民事訴訟法（6，大幅擴充）════
    'civ_proc_管轄':  dict(name='民訴｜管轄', sf='civil',
                         kw=['管轄','土地管轄','事物管轄','移送管轄','專屬管轄','合意管轄','應訴管轄','指定管轄','國際管轄','管轄競合','不便利法庭','管轄恒定'], imp=5),
    'civ_proc_當事人': dict(name='民訴｜當事人與訴訟參加', sf='civil',
                          kw=['當事人能力','訴訟能力','法定代理','選定當事人','訴訟擔當','參加訴訟','輔助參加','獨立參加','固有必要共同訴訟','類似必要共同訴訟','當事人適格','訴訟代理人','選定人'], imp=5),
    'civ_proc_程序':  dict(name='民訴｜訴訟程序本論', sf='civil',
                         kw=['起訴','訴之聲明','訴訟標的','既判力','言詞辯論','裁判','調解','確認之訴','給付之訴','形成之訴','訴訟費用','確認利益','訴之合併','反訴','訴之撤回','一事不再理','訴訟繫屬','中間判決'], imp=5),
    'civ_proc_證據':  dict(name='民訴｜證據', sf='civil', kw=['舉證責任','書證','人證','鑑定','自認','文書提出義務','勘驗','調查證據','抗辯事實','事實推定','法律推定','舉證分配'], imp=4),
    'civ_proc_上訴':  dict(name='民訴｜上訴與再審', sf='civil',
                         kw=['上訴','抗告','再審','第三審','廢棄','發回','違背法令','許可上訴','上訴利益','小額訴訟上訴','移審'], imp=4),
    'civ_proc_保全':  dict(name='民訴｜保全程序與特殊程序', sf='civil',
                         kw=['假扣押','假處分','督促程序','支付命令','保全程序','本票裁定','非訟','簡易程序','假執行','撤銷假扣押','保全必要'], imp=4),
    'civ_proc_家事':  dict(name='民訴｜家事事件程序', sf='civil',
                         kw=['家事','家事事件法','家事法院','家事調解','家事程序','婚姻事件','親子事件','收養許可','監護宣告','宣告死亡','失蹤宣告','家事非訟','家事審判','家事調查官','親權酌定','子女監護','家庭暴力'], imp=3),
    # ════ 公司法（5，依考選部大綱：通則/有限公司/股份有限組織/股份有限重組/關係企業）════
    'corp_通則':      dict(name='公司法｜通則與有限公司', sf='commercial', kw=['有限公司','公司名稱','無限公司','兩合公司','外國公司','公司負責人','發起人','分公司','盈餘分派','公司種類','股份有限公司設立','公司登記','經理人','公司章程','清算人'], imp=5),
    'corp_股份_組織': dict(name='公司法｜股份有限公司－組織', sf='commercial',
                         kw=['股東會','董事會','監察人','董事','表決權','股東名簿','電子投票','委託書','選任董事','股東決議','臨時會','常會','股東訴訟','大股東','罷免董事','directors','board','shareholders','獨立董事','審計委員會','薪資報酬委員會'], imp=5),
    'corp_股份_資本': dict(name='公司法｜股份有限公司－資本與股份', sf='commercial',
                         kw=['股票','股份','現金增資','私募','特別股','股份轉讓','股份回購','認購','減資','盈餘分配','發行新股','公司債','實收資本','股份平等','corporate','incorporation'], imp=5),
    'corp_股份_重組': dict(name='公司法｜股份有限公司－重組與解散', sf='commercial',
                         kw=['公司重整','合併','分割','閉鎖性','解散','清算','公司清算人','消滅公司','存續公司','股份轉換','股份交換','簡易合併','短式合併','重整人','重整監督人','清算人'], imp=4),
    'corp_關係企業':  dict(name='公司法｜關係企業', sf='commercial',
                         kw=['關係企業','控制公司','從屬公司','控制與從屬','相互投資','控制關係','關係報告書','合併財務報表','少數股東','從屬關係','轉投資','子公司','母公司','企業集團','控制股東','關係人交易','持股比例','關係人'], imp=4),
    # ════ 票據法（4，依考選部大綱：總論/匯票/本票/支票）════
    'bill_總論':      dict(name='票據法｜票據總論', sf='commercial',
                         kw=['票據行為','票據關係','票據抗辯','票據債務','票據時效','票據無因性','善意取得','偽造','變造','票據喪失','公示催告','票據代理','空白票據','票據法','票據背書','票據保證'], imp=4),
    'bill_匯票':      dict(name='票據法｜匯票', sf='commercial',
                         kw=['匯票','承兌','到期日','追索權','拒絕証書','承兌人','參加承兌','參加付款','複本','謄本','定期匯票','見票後定期匯票','付款人','受款人','匯票發票人'], imp=4),
    'bill_本票':      dict(name='票據法｜本票', sf='commercial',
                         kw=['本票','見票即付','本票裁定','強制執行本票','本票發票人','見票後定期本票','一覽即付','本票金額','本票到期'], imp=4),
    'bill_支票':      dict(name='票據法｜支票', sf='commercial',
                         kw=['支票','平行線支票','保付支票','遠期支票','止付','退票','拒絕付款支票','支票提示','禁止背書轉讓支票','支票效力','支票發票人','支票存款'], imp=4),
    # ════ 海商法（1，不變）════
    'sea_海商':       dict(name='海商法', sf='commercial', kw=['船舶','載貨','船長','海難','共同海損','提單','海商','運送人','旅客','運費','船舶碰撞','海上保險','救助','貨物滅失','船舶所有人','大副','航行','港口','碰撞','海員','單獨海損','船務代理','拖帶','救助報酬','海商法','船舶抵押','海上留置','傭船','船貨'], imp=3),
    # ════ 保險法（4，依考選部大綱：總則/保險契約/財產保險/人身保險）════
    'ins_總則':       dict(name='保險法｜總則', sf='commercial',
                         kw=['保險利益','複保險','再保險','超額保險','不足額保險','代位','保險分類','保險費返還','保險法','定值保險','不定值保險','損失補償原則'], imp=4),
    'ins_契約':       dict(name='保險法｜保險契約', sf='commercial',
                         kw=['保險契約','要保人','被保險人','保險費','告知義務','危險增加','復效','解約','免責條款','最大誠信','同意主義','契約解釋','保單','特約條款','保費交付','危險發生'], imp=4),
    'ins_財產':       dict(name='保險法｜財產保險', sf='commercial',
                         kw=['財產保險','火災保險','責任保險','海上保險','保證保險','產險','陸空保險','保險標的','全損','分損','代位求償','保險事故','標的物滅失'], imp=4),
    'ins_人身':       dict(name='保險法｜人身保險', sf='commercial',
                         kw=['人身保險','人壽保險','健康保險','傷害保險','年金保險','壽險','受益人','死亡保險','保額','保單借款','解約金','自殺免責','保險金','人身保險受益人'], imp=4),
    # ════ 強制執行法（4，依考選部大綱：總則/金錢債權/非金錢債權/假扣押假處分）════
    'exec_總則':      dict(name='強制執行法｜總則', sf='commercial',
                         kw=['執行名義','聲請執行','強制執行法','執行費','拘提管收','執行救濟','聲明異議','債務人異議之訴','第三人異議之訴','執行當事人','財產開示','限制住居','執行機關','執行名義繫屬'], imp=4),
    'exec_金錢':      dict(name='強制執行法｜金錢債權執行', sf='commercial',
                         kw=['查封','拍賣','分配','分配表','優先受償','不動產執行','動產執行','強制管理','強制拍賣','扣押命令','參與分配','底價','拍定','超額查封','查封效力','金錢債權'], imp=4),
    'exec_非金錢':    dict(name='強制執行法｜非金錢債權執行', sf='commercial',
                         kw=['交付動產','移交不動產','行為請求權','不行為請求權','意思表示執行','替代執行','代替執行','物之交付','非金錢債權','財產分割執行','交付子女'], imp=3),
    'exec_保全':      dict(name='強制執行法｜假扣押假處分執行', sf='commercial',
                         kw=['假扣押執行','假處分執行','保全執行','假執行','撤銷假扣押','假扣押裁定','假處分裁定','保全程序','執行競合','免假執行'], imp=3),
    # ════ 證券交易法（3，依考選部大綱：發行/不法/監理）════
    'sec_發行':       dict(name='證券交易法｜有價證券發行', sf='commercial',
                         kw=['公開說明書','募集發行','申報生效','強制分散','轉售限制','轉換公司債','認購新股','發行人責任','核准發行','承銷商','興櫃','創櫃','上市申請','上櫃申請','初次上市'], imp=4),
    'sec_不法':       dict(name='證券交易法｜不法行為', sf='commercial',
                         kw=['內線交易','操縱市場','財報不實','短線交易','內部人','重大消息','消息公開前','財務報告不實','操縱','虛偽','歸入權','刑事責任','懲罰性賠償','不法行為','157條','155條','民事賠償責任','重大未公開'], imp=4),
    'sec_監理':       dict(name='證券交易法｜證券監理', sf='commercial',
                         kw=['公開收購','大量持股','資訊揭露','委託書','公司治理','獨立董事','審計委員會','薪資報酬委員會','薪資報酬','券商','交易所','持股申報','公開收購申報','securities','underwriter','disclosure'], imp=4),
    # ════ 法學英文（1，不變）════
    'eng_英文':       dict(name='法學英文', sf='commercial', kw=['civil','criminal','constitution','tort','contract','plaintiff','defendant','liability','corporation','shareholder','director','securities','offering','offer','consideration','breach','damages','remedy','negligence','property','equity','obligation','regulation','statute','common law','court','judicial','injunction','evidence','testimony','appeal','penalty','insurance','fiduciary','proxy','underwriter','lawsuit','attorney','counsel','client','due process','equal protection','scrutiny','sentencing','burden of proof','hearsay','warrant','seizure','reasonable','presumption','allegation','complaint','verdict','acquittal','conviction','majority','minority','board of directors','articles','incorporation','nuisance','trespass','misrepresentation'], imp=3),
}

_LAW_FALLBACK = {
    '刑法':       'crim_競合刑罰',
    '刑事訴訟法': 'cpc_偵查',
    '法律倫理':   'ethics_律師',
    '憲法':       'const_基本權',
    '行政法':     'admin_行政訴訟',
    '國際公法':   'intl_公法_主體',
    '國際私法':   'intl_私法_總論',
    '民法':       'civil_債總',
    '民事訴訟法': 'civ_proc_程序',
    '公司法':     'corp_股份_組織',
    '票據法':     'bill_總論',
    '海商法':     'sea_海商',
    '保險法':     'ins_總則',
    '強制執行法': 'exec_總則',
    '證券交易法': 'sec_不法',
    '法學英文':   'eng_英文',
}

def classify_topic(question, options_str, subj, law_subject):
    text = question + ' ' + options_str
    # 英文題優先檢查（法學英文科目）
    if law_subject == '法學英文':
        return 'eng_英文'
    best, best_score = None, -1
    for tid, info in TOPICS.items():
        if TOPIC_TO_LAW.get(tid) != law_subject: continue  # 只在該科目的主題裡比對
        score = sum(1 for kw in info['kw'] if kw in text)
        if score > best_score:
            best_score, best = score, tid
    if best is None or best_score == 0:
        return _LAW_FALLBACK.get(law_subject, 'crim_競合刑罰')
    return best

# ── 分科題號範圍規則 ────────────────────────────────────────
# 刑法考卷：結構固定，所有年份相同
_CRIMINAL_RANGES = [
    (1, 40, '刑法'),
    (41, 60, '刑事訴訟法'),
    (61, 75, '法律倫理'),
]
# 憲法考卷：依年份有微調
_CONSTITUTIONAL_RANGES = {
    107: [(1,22,'憲法'), (23,55,'行政法'), (56,65,'國際公法'), (66,75,'國際私法')],
}
_CONSTITUTIONAL_DEFAULT = [(1,20,'憲法'), (21,55,'行政法'), (56,65,'國際公法'), (66,75,'國際私法')]
# 民法考卷：民訴起始題號（之前全是民法）
_CIVIL_BOUNDARY = {107: 53}
_CIVIL_DEFAULT_BOUNDARY = 51
# 商法考卷：固定結構（公司法→保險法→票據法→証交→強執→法英）
_COMMERCIAL_RANGES = [
    (1,  15, '公司法'),
    (16, 25, '保險法'),
    (26, 35, '票據法'),
    (36, 45, '證券交易法'),
    (46, 55, '強制執行法'),
    (56, 99, '法學英文'),
]

def get_law_subject(group, year, num, fallback):
    if group == 'criminal':
        for lo, hi, ls in _CRIMINAL_RANGES:
            if lo <= num <= hi:
                return ls
        return '刑法'
    if group == 'constitutional':
        ranges = _CONSTITUTIONAL_RANGES.get(year, _CONSTITUTIONAL_DEFAULT)
        for lo, hi, ls in ranges:
            if lo <= num <= hi:
                return ls
        return ranges[-1][2]
    if group == 'civil':
        boundary = _CIVIL_BOUNDARY.get(year, _CIVIL_DEFAULT_BOUNDARY)
        return '民法' if num < boundary else '民事訴訟法'
    if group == 'commercial':
        for lo, hi, ls in _COMMERCIAL_RANGES:
            if lo <= num <= hi:
                return ls
        return '公司法'
    return fallback

def parse_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    questions, seen = [], set()
    blocks = re.split(r'\n-{20,}\n', content)
    for block in blocks:
        block = block.strip()
        if not block: continue
        lines = [l.strip() for l in block.splitlines() if l.strip()]
        if not lines: continue
        # Find question line (first block may include file header before question 1)
        q_start = next((i for i, l in enumerate(lines) if re.match(r'^第\s*\d+\s*題', l)), -1)
        if q_start < 0: continue
        lines = lines[q_start:]
        m = re.match(r'^第\s*(\d+)\s*題', lines[0])
        if not m: continue
        q_num = int(m.group(1))
        if q_num in seen: continue
        seen.add(q_num)
        q_lines, opts, answer = [], {}, ''
        for line in lines[1:]:
            if   re.match(r'^\(A\)', line): opts['A'] = line[3:].strip()
            elif re.match(r'^\(B\)', line): opts['B'] = line[3:].strip()
            elif re.match(r'^\(C\)', line): opts['C'] = line[3:].strip()
            elif re.match(r'^\(D\)', line): opts['D'] = line[3:].strip()
            elif re.match(r'^答案[：:]', line): answer = re.sub(r'^答案[：:]', '', line).strip()
            elif not opts: q_lines.append(line)
        if q_lines and len(opts) == 4 and answer:
            questions.append({'num': q_num, 'question': ' '.join(q_lines), 'options': opts, 'answer': answer})
    return questions

def main():
    script_dir = Path(__file__).parent
    src_dir = script_dir.parent / '一試考古題'
    all_questions = []
    topic_year_count = defaultdict(set)
    for filepath in sorted(src_dir.glob('*.txt')):
        fn   = filepath.name
        year = get_year(fn)
        subj = exam_subject(fn)
        qs   = parse_file(filepath)
        print(f'  {fn}: {len(qs)} 題')
        for q in qs:
            opts_str = ' '.join(q['options'].values())
            law_sub = get_law_subject(subj, year, q['num'], '其他')  # 先確定科目
            tid = classify_topic(q['question'], opts_str, subj, law_sub)  # 再在該科目主題內比對
            topic_year_count[tid].add(year)
            q.update({
                'year': year, 'subject': subj,
                'topic': tid,
                'topic_name': TOPICS.get(tid, {}).get('name', '其他').split('｜')[-1],
                'law_subject': law_sub,
                'base_importance': TOPICS.get(tid, {}).get('imp', 3),
                'difficulty': 3,
                'id': f"{year}_{subj}_{q['num']}"
            })
            all_questions.append(q)

    for q in all_questions:
        years_count = len(topic_year_count[q['topic']])
        q['importance'] = min(5, q['base_importance'] + (1 if years_count >= 6 else 0))

    # 主題彙整
    topic_counts = defaultdict(int)
    law_counts = defaultdict(int)
    for q in all_questions:
        topic_counts[q['topic']] += 1
        law_counts[q['law_subject']] += 1

    topics_out = {}
    for tid, info in TOPICS.items():
        law_sub = TOPIC_TO_LAW.get(tid, '其他')
        topics_out[tid] = {
            'name': info['name'], 'short_name': info['name'].split('｜')[-1],
            'subject': info['sf'] or '', 'law_subject': law_sub,
            'importance': info['imp'], 'count': topic_counts.get(tid, 0),
            'kw': info.get('kw', [])
        }

    total = len(all_questions)
    years = sorted(set(q['year'] for q in all_questions))
    print(f'\n總計：{total} 題，年份：{years}')

    output = {
        'questions': all_questions,
        'topics': topics_out,
        'law_subjects': LAW_SUBJECTS,
        'law_counts': dict(law_counts),
        'years': years,
        'total': total
    }

    out_path = script_dir / 'js' / 'questions_data.js'
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write('window.QDB = ')
        f.write(json.dumps(output, ensure_ascii=False))
        f.write(';\n')
    print(f'已輸出：{out_path}')

if __name__ == '__main__':
    main()
