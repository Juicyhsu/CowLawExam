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
    'crim_罪刑法定':'刑法','crim_構成要件':'刑法','crim_違法性':'刑法',
    'crim_罪責':'刑法','crim_未遂':'刑法','crim_共犯':'刑法',
    'crim_競合刑罰':'刑法','crim_生命身體':'刑法','crim_性侵自由':'刑法',
    'crim_財產':'刑法','crim_公共危險':'刑法','crim_職務偽造':'刑法',
    'cpc_偵查強制':'刑事訴訟法','cpc_證據':'刑事訴訟法',
    'cpc_審判':'刑事訴訟法','cpc_上訴救濟':'刑事訴訟法','cpc_特殊':'刑事訴訟法',
    'ethics_律師':'法律倫理',
    'const_基本權':'憲法','const_違憲審查':'憲法','const_統治':'憲法',
    'admin_總論':'行政法','admin_行為':'行政法','admin_罰':'行政法',
    'admin_救濟':'行政法','admin_地方':'行政法',
    'intl_公法':'國際公法','intl_私法':'國際私法',
    'civil_總則':'民法','civil_債總':'民法','civil_買賣租賃':'民法',
    'civil_其他債各':'民法','civil_侵權不當':'民法','civil_物權':'民法',
    'civil_親屬':'民法','civil_繼承':'民法',
    'civ_proc_程序':'民事訴訟法','civ_proc_證據':'民事訴訟法','civ_proc_上訴':'民事訴訟法',
    'corp_通則':'公司法','corp_股份':'公司法',
    'bill_票據':'票據法','sea_海商':'海商法','ins_保險':'保險法',
    'exec_強執':'強制執行法','sec_證交':'證券交易法','eng_英文':'法學英文',
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
    'cpc_偵查強制':   dict(name='刑訴｜偵查與強制處分', sf='criminal', kw=['搜索','扣押','逮捕','羈押','偵查','票狀','傳喚','具保','拘提','通緝','限制出境','搜索票','緊急搜索','無票搜索','必要處分','限制出境出海','扣押物'], imp=5),
    'cpc_證據':       dict(name='刑訴｜證據法則', sf='criminal', kw=['證據','自白','傳聞','非任意性','鑑定','勘驗','證據能力','不自證己罪','補強','傳聞法則','直接審理','詰問','交互詰問','對質','書面陳述','排除法則'], imp=5),
    'cpc_審判':       dict(name='刑訴｜起訴審判程序', sf='criminal', kw=['起訴','公訴','不起訴','緩起訴','準備程序','言詞辯論','辯護','蒞庭','告訴','告發','辯護人','強制辯護','公訴分擔'], imp=4),
    'cpc_上訴救濟':   dict(name='刑訴｜上訴與非常救濟', sf='criminal', kw=['上訴','抗告','再審','非常上訴','第三審','發回','發交','確定判決','廢棄','違背法令','一事不再理'], imp=4),
    'cpc_特殊':       dict(name='刑訴｜特殊程序', sf='criminal', kw=['簡易程序','協商','簡式審判','國民法官','緩刑','假釋','保安處分','強制工作','監護處分','刑事補償','少年刑事'], imp=3),
    'ethics_律師':    dict(name='律師倫理', sf='criminal', kw=['律師','倫理','保密','利益衝突','律師法','職業道德','依賴人','受任人','懲戒','中華民國律師','律師公會','職務規定'], imp=3),
    'const_基本權':   dict(name='憲法｜基本權保障', sf='constitutional', kw=['基本權','平等','人身自由','言論自由','財產權','工作權','集會','宗教','隱私','比例原則','人格權','名譽權','受教育','生存權','身體自由','遷徙自由','資訊隱私','基本人權','隱私權','個人資料','秘密通訊'], imp=5),
    'const_違憲審查': dict(name='憲法｜違憲審查與釋憲', sf='constitutional', kw=['違憲','大法官','釋字','比例原則','審查基準','憲法法庭','違憲宣告','裁判憲法訴願','暫時處分','合憲解釋','嚴格審查','中度審查','寬鬆審查','法規範憲法審查'], imp=5),
    'const_統治':     dict(name='憲法｜統治機構', sf='constitutional', kw=['立法院','行政院','司法院','總統','五院','副署','覆議','國情報告','考試院','監察院','三讀','程序委員會','閣揆','解散','倒閣','不信任案','緊急命令','戒嚴','國防','基本國策','軍事','國軍','行政院院長','修憲','憲政機關'], imp=4),
    'admin_總論':     dict(name='行政法｜基本原則', sf='constitutional', kw=['依法行政','法律保留','法律優位','裁量','信賴保護','誠信原則','比例原則','行政自我拘束','授權明確','行政機關','機關組織','行政院組織','中央行政','行政組織','行政程序','行政效率','一致性原則','組織基準法','獨立機關'], imp=5),
    'admin_行為':     dict(name='行政法｜行政行為', sf='constitutional', kw=['行政處分','行政契約','行政命令','法規命令','行政指導','附款','行政規則','職權命令','授權命令','私法形式','事實行為','一般處分','多階段行政處分','裁量處分','行政行為','委任行政','行政委託'], imp=5),
    'admin_罰':       dict(name='行政法｜行政罰', sf='constitutional', kw=['行政罰','裁罰','行政秩序罰','沒入','罰鍰','一行為不二罰','行政罰法','裁處期間','吊照','停業','連續罰'], imp=4),
    'admin_救濟':     dict(name='行政法｜行政救濟', sf='constitutional', kw=['訴願','行政訴訟','撤銷訴訟','課予義務','確認訴訟','國家賠償','訴願決定','行政法院','先行訴願','徵收補償','損失補償','違法行政','撤銷','行政爭訟','聲請停止執行'], imp=5),
    'admin_地方':     dict(name='行政法｜地方制度', sf='constitutional', kw=['地方制度','地方自治','直轄市','縣市','自治條例','地方自治法','自治事項','委辦事項','自治法規','鄉鎮','行政區','自治團體'], imp=3),
    'intl_公法':      dict(name='國際公法', sf='constitutional', kw=['國際法','條約','主權','領海','公海','國際組織','外交','締結','習慣國際法','聯合國','外交保護','批准','加入','國際人道法','引渡','外交豁免','國際刑事法院','條約法'], imp=4),
    'intl_私法':      dict(name='國際私法', sf='constitutional', kw=['涉外','準據法','連結因素','反致','公序良俗','外國法','法律選擇','本國法','住所地法','屬人法','屬地法','行為地法','國籍','慣居地','涉外民事法律適用法'], imp=4),
    'civil_總則':     dict(name='民法｜總則', sf='civil', kw=['法律行為','意思表示','行為能力','代理','時效','條件','虛偽','通謀','消滅時效','請求權','限制行為能力','無行為能力','錯誤','詐欺','脅迫','撤銷','無效','有效成立','法人','社團','財團'], imp=5),
    'civil_債總':     dict(name='民法｜債法總論', sf='civil', kw=['債之發生','連帶','保證','抵銷','給付遲延','給付不能','不完全給付','情事變更','契約','清償','提存','代物清償','債務承擔','契約終止','解除','第三人利益契約','契約關係消滅','連帶債務','返還','讓與','債權讓與','通知','讓與通知','清算','履行輔助'], imp=5),
    'civil_買賣租賃': dict(name='民法｜買賣與租賃', sf='civil', kw=['買賣','租賃','出租','承租','瑕疵擔保','危險負擔','物之瑕疵','租期','終止租約','地上物','不動產買賣','一物數賣','標的物滅失'], imp=4),
    'civil_其他債各': dict(name='民法｜其他典型契約', sf='civil', kw=['消費借貸','使用借貸','委任','承攬','贈與','寄託','雇傭','居間','旅遊','合會','和解','定作人','承攬人','受任人','委任人'], imp=4),
    'civil_侵權不當': dict(name='民法｜侵權行為與不當得利', sf='civil', kw=['侵權行為','不當得利','無因管理','損害賠償','慰撫金','非財產上損害','共同侵權','僱主責任','商品製造人','動物所有人','工作物','受僱人','連帶損害賠償'], imp=5),
    'civil_物權':     dict(name='民法｜物權', sf='civil', kw=['物權','所有權','地上權','抵押權','質權','留置權','占有','物權法定','共有','分管','共有人','先買權','抵押物','抵押設定','擔保物權','用益物權','典權','農育權','不動產登記'], imp=5),
    'civil_親屬':     dict(name='民法｜親屬法', sf='civil', kw=['婚姻','結婚','離婚','扶養','監護','收養','夫妻財產','宣告死亡','認領','非婚生子女','父母子女','行使親權','撫養費','剩餘財產','夫妻財產制'], imp=4),
    'civil_繼承':     dict(name='民法｜繼承法', sf='civil', kw=['繼承','遺囑','遺產','遺贈','應繼分','特留分','拋棄繼承','限定繼承','遺產管理人','繼承人','代位繼承','被繼承人','遺囑執行人','自書遺囑','公證遺囑'], imp=4),
    'civ_proc_程序':  dict(name='民訴｜訴訟程序', sf='civil', kw=['管轄','起訴','言詞辯論','裁判','調解','既判力','訴訟繫屬','訴訟標的','訴訟費用','確認之訴','給付之訴','形成之訴','訴訟代理人','共同訴訟','必要共同訴訟','當事人適格','訴之聲明'], imp=5),
    'civ_proc_證據':  dict(name='民訴｜證據', sf='civil', kw=['舉證責任','書證','人證','鑑定','自認','文書提出義務','勘驗','調查證據','抗辯事實','事實推定','法律推定','舉證分配'], imp=4),
    'civ_proc_上訴':  dict(name='民訴｜上訴與特殊程序', sf='civil', kw=['上訴','抗告','再審','督促程序','假扣押','假處分','廢棄','發回','小額訴訟','第三審不得上訴','許可上訴','移送審判'], imp=4),
    'corp_通則':      dict(name='公司法｜通則與有限公司', sf='commercial', kw=['有限公司','公司名稱','章程','解散','清算','出資','公司債','無限公司','兩合公司','外國公司','公司負責人','發起人','分公司','實收資本','盈餘分派','公司法','公司清算人','轉投資'], imp=5),
    'corp_股份':      dict(name='公司法｜股份有限公司', sf='commercial', kw=['股份有限','股東會','董事會','監察人','股票','特別股','閉鎖性','股份轉讓','盈餘分配','表決權','股東名簿','現金增資','合併','分割','董事','大股東','電子投票','委託書','選任董事','股東決議','臨時會','常會','股東訴訟','shareholders','directors','board','corporate'], imp=5),
    'bill_票據':      dict(name='票據法', sf='commercial', kw=['票據','匯票','本票','支票','背書','承兌','發票人','執票人','付款人','保證人','背書人','承兌人','拒絕付款','止付','票據時效','票據行為','票據關係','到期日','見票','提示','拒付','公示催告','票據抗辯','票據債務'], imp=4),
    'sea_海商':       dict(name='海商法', sf='commercial', kw=['船舶','載貨','船長','海難','共同海損','提單','海商','運送人','旅客','運費','船舶碰撞','海上保險','救助','貨物滅失','船舶所有人','大副','航行','港口','碰撞','海員','單獨海損','船務代理','拖帶','救助報酬','海商法','船舶抵押','海上留置','傭船','船貨'], imp=3),
    'ins_保險':       dict(name='保險法', sf='commercial', kw=['保險','要保人','被保險人','保險費','保險契約','受益人','保險人','理賠','保額','壽險','產險','告知義務','危險增加','複保險','代位','復效','解約','保險事故','保險法','免責條款','超額保險','不足額保險','人身保險','財產保險'], imp=4),
    'exec_強執':      dict(name='強制執行法', sf='commercial', kw=['強制執行','查封','拍賣','分配','執行名義','執行命令','執行員','異議','強制拍賣','強制管理','分配表','優先受償','徵收','徵收補償','不動產執行','動產執行','債務人','債權人','聲請執行','扣押','強執','清償','補償費','土地徵收'], imp=4),
    'sec_證交':       dict(name='證券交易法', sf='commercial', kw=['證券','有價證券','內線交易','公開收購','上市','上櫃','承銷','操縱市場','財報不實','公開說明書','公司治理','交易所','券商','申報','資訊揭露','大量持股','公開發行','私募','發行人','認購','轉換公司債','securities','issuer','underwriter','disclosure'], imp=4),
    'eng_英文':       dict(name='法學英文', sf='commercial', kw=['civil','criminal','constitution','tort','contract','plaintiff','defendant','liability','corporation','shareholder','director','securities','offering','offer','consideration','breach','damages','remedy','negligence','property','equity','obligation','regulation','statute','common law','court','judicial','injunction','evidence','testimony','appeal','penalty','insurance','fiduciary','proxy','underwriter','lawsuit','attorney','counsel','client','due process','equal protection','scrutiny','sentencing','burden of proof','hearsay','warrant','seizure','reasonable','presumption','allegation','complaint','verdict','acquittal','conviction','majority','minority','board of directors','articles','incorporation','nuisance','trespass','misrepresentation'], imp=3),
}

_SUBJ_FALLBACK = {
    'criminal':       'crim_競合刑罰',
    'constitutional': 'const_統治',
    'civil':          'civil_債總',
    'commercial':     'corp_通則',
}

def classify_topic(question, options_str, subj):
    text = question + ' ' + options_str
    # 英文題優先檢查（commercial 科目英文比例高）
    if subj == 'commercial':
        eng_alpha = sum(1 for c in text if c.isascii() and c.isalpha())
        all_alpha  = sum(1 for c in text if c.isalpha())
        if all_alpha > 10 and eng_alpha / all_alpha > 0.45:
            return 'eng_英文'
    best, best_score = None, -1
    for tid, info in TOPICS.items():
        if info['sf'] and info['sf'] != subj: continue
        score = sum(1 for kw in info['kw'] if kw in text)
        if score > best_score:
            best_score, best = score, tid
    if best is None or best_score == 0:
        return _SUBJ_FALLBACK.get(subj, 'crim_競合刑罰')
    return best

def parse_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    questions, seen = [], set()
    blocks = re.split(r'\n-{20,}\n', content)
    for block in blocks:
        block = block.strip()
        if not block or '考古題' in block or '題數：' in block: continue
        lines = [l.strip() for l in block.splitlines() if l.strip()]
        if not lines: continue
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
            tid = classify_topic(q['question'], opts_str, subj)
            topic_year_count[tid].add(year)
            law_sub = TOPIC_TO_LAW.get(tid, '其他')
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
