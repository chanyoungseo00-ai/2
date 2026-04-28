import streamlit as st
import pandas as pd
import numpy as np
import io
import random
import itertools

# 화면 설정 (반드시 최상단 배치)
st.set_page_config(page_title="그라운드골프 통합 시스템", layout="wide")

# ==========================================
# [기능 1] 대진표 자동 편성 로직
# ==========================================
def assign_teams_and_orders(df, holes_per_field=8, players_per_team=6, match_type="개인전"):
    working_df = df.copy()
    num_teams = (len(working_df) + players_per_team - 1) // players_per_team
    if num_teams == 0: 
        return pd.DataFrame(), 0
    
    teams = [[] for _ in range(num_teams)]
    fields = ['청', '백', '홍', '황']
    
    # 1. 조 편성 (지역 중복 방지 및 성별 배분)
    if match_type == "개인전":
        players = working_df.to_dict('records')
        r_counts = working_df['지역'].value_counts().to_dict()
        players.sort(key=lambda x: (r_counts.get(x['지역'], 0), x['지역']), reverse=True)
        for p in players:
            best_team = min(teams, key=lambda t: (sum(1 for x in t if x['지역'] == p['지역']), len(t)))
            best_team.append(p)
    else: 
        # 단체전: 모든 조에 여자 선수 2명 이상 필수 포함 규정 적용
        females = working_df[working_df['성별'] == '여'].to_dict('records')
        males = working_df[working_df['성별'] == '남'].to_dict('records')
        for team in teams:
            for _ in range(2):
                if not females: break
                min_overlap = min(sum(1 for x in team if x['지역'] == f['지역']) for f in females)
                for i, f in enumerate(females):
                    if sum(1 for x in team if x['지역'] == f['지역']) == min_overlap:
                        team.append(females.pop(i)); break
        rem = females + males
        rem_counts = pd.Series([p['지역'] for p in rem]).value_counts().to_dict()
        rem.sort(key=lambda x: (rem_counts.get(x['지역'], 0), x['지역']), reverse=True)
        for p in rem:
            best_team = min(teams, key=lambda t: (sum(1 for x in t if x['지역'] == p['지역']), len(t)))
            best_team.append(p)

    # 2. 타순 평탄화 (지역별 타순 순환 배치)
    region_order_count = {r: {i: 0 for i in range(1, players_per_team + 1)} for r in working_df['지역'].unique()}
    for team in teams:
        avail_orders = list(range(1, players_per_team + 1))
        best_perm = None
        best_score = float('inf')
        perms = [random.sample(avail_orders, len(team)) for _ in range(2000)]
        for perm in perms:
            score = 0
            for i, p in enumerate(team):
                score += region_order_count[p['지역']].get(perm[i], 0) ** 2
            if score < best_score:
                best_score = score
                best_perm = perm
                if score == 0: break
        for i, p in enumerate(team):
            p['타순'] = best_perm[i]
            region_order_count[p['지역']][best_perm[i]] += 1

    # 3. 구장 정렬 및 결과 생성 (청 ➔ 백 ➔ 홍 ➔ 황 순서 보장)
    final_roster = []
    for idx, team in enumerate(teams):
        # 구장 배정 (0:청, 1:백, 2:홍, 3:황)
        f_idx = idx % 4
        field_name = fields[f_idx]
        hole = (idx // 4) % holes_per_field + 1
        round_id = (idx // (4 * holes_per_field)) + 1
        
        s_hole = f"{field_name}구장 {hole}홀"
        set_name = f"{round_id}그룹 {field_name}구장" if len(teams) > holes_per_field * 4 else f"{field_name}구장"
            
        for p in team:
            final_roster.append({
                '진행 그룹': set_name, '팀': f"{match_type} {idx+1}조", 
                '구장': field_name, '홀': hole, '타순': p['타순'], 
                '지역': p['지역'], '이름': p['이름'], '성별': p['성별'],
                '_r': round_id, '_f': f_idx, '_h': hole
            })
            
    # ★ 핵심 정렬: 구장 순서(청➔백➔홍➔황)와 홀 순서를 최우선으로 정렬
    res_df = pd.DataFrame(final_roster).sort_values(
        by=['_r', '_f', '_h', '타순']
    ).reset_index(drop=True)
    
    return res_df.drop(columns=['_r', '_f', '_h']), num_teams, region_order_count

# ==========================================
# [기능 2] 인쇄용 엑셀 출력 양식
# ==========================================
def create_print_excel(df, match_type, holes_cnt):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        workbook = writer.book
        header_fmt = workbook.add_format({'bold': True, 'bg_color': '#D9EAD3', 'border': 1, 'align': 'center'})
        cell_fmt = workbook.add_format({'border': 1, 'align': 'center'})
        
        # 구장별 시트 생성
        for f_name in ['청', '백', '홍', '황']:
            f_df = df[df['구장'] == f_name]
            if f_df.empty: continue
            
            worksheet = workbook.add_worksheet(f"{f_name}구장 대진표")
            worksheet.set_column('A:N', 10)
            worksheet.write(0, 0, f"제18회 대한체육회장배 {match_type} 대진표 ({f_name}구장)", workbook.add_format({'bold': True, 'font_size': 14}))
            
            row = 3
            # 2개 홀씩 짝지어서 2단 레이아웃 배치
            for h in range(1, holes_cnt + 1, 2):
                h1_data = f_df[f_df['홀'] == h]
                h2_data = f_df[f_df['홀'] == h+1]
                
                # 헤더
                heads = ['홀', '타순', '지역', '이름', '성별', '심판']
                for c, text in enumerate(heads):
                    worksheet.write(row, c, text, header_fmt)
                    worksheet.write(row, c+7, text, header_fmt)
                row += 1
                
                for i in range(max(len(h1_data), len(h2_data), 6)):
                    if i < len(h1_data):
                        p = h1_data.iloc[i]
                        worksheet.write(row+i, 0, h if i==0 else "", cell_fmt)
                        worksheet.write(row+i, 1, p['타순'], cell_fmt)
                        worksheet.write(row+i, 2, p['지역'], cell_fmt)
                        worksheet.write(row+i, 3, p['이름'], cell_fmt)
                        worksheet.write(row+i, 4, p['성별'], cell_fmt)
                        worksheet.write(row+i, 5, "", cell_fmt)
                    if i < len(h2_data):
                        p = h2_data.iloc[i]
                        worksheet.write(row+i, 7, h+1 if i==0 else "", cell_fmt)
                        worksheet.write(row+i, 8, p['타순'], cell_fmt)
                        worksheet.write(row+i, 9, p['지역'], cell_fmt)
                        worksheet.write(row+i, 10, p['이름'], cell_fmt)
                        worksheet.write(row+i, 11, p['성별'], cell_fmt)
                        worksheet.write(row+i, 12, "", cell_fmt)
                row += max(len(h1_data), len(h2_data), 6) + 1
    return output.getvalue()

# ==========================================
# [메인 화면]
# ==========================================
st.sidebar.title("⛳ 운영 통합 시스템")
mode = st.sidebar.radio("작업 선택", ["대진표 편성", "대회 채점"])

if mode == "대진표 편성":
    st.title("⛳ 대진표 자동 편성 (청➔백➔홍➔황 정렬)")
    m_type = st.sidebar.radio("편성 부문", ["개인전", "단체전"])
    h_cnt = st.sidebar.radio("출발홀 수", [6, 7, 8], index=2)
    p_cnt = st.sidebar.radio("조당 인원", [6, 7, 8], index=0)
    
    up_file = st.file_uploader("선수 명단 엑셀 업로드", type=["xlsx"])
    
    if up_file and st.button("🚀 대진표 생성 및 타순 검증 실행"):
        df_raw = pd.read_excel(up_file)
        if '이름' not in df_raw.columns and '성명' not in df_raw.columns:
            df_raw = pd.read_excel(up_file, skiprows=1)
        
        df_raw.columns = df_raw.columns.astype(str).str.strip()
        df_raw = df_raw.rename(columns={'소속': '지역', '성명': '이름'})
        
        if not {'지역', '이름', '성별'}.issubset(df_raw.columns):
            st.error("❌ 엑셀에 [지역], [이름], [성별] 열이 없습니다.")
        else:
            df_clean = df_raw.dropna(subset=['지역', '이름', '성별'])[['지역', '이름', '성별']].copy()
            res, t_cnt, order_stats = assign_teams_and_orders(df_clean, h_cnt, p_cnt, m_type)
            
            st.subheader(f"✅ {m_type} 편성 완료 (총 {t_cnt}개 조)")
            st.dataframe(res, use_container_width=True)
            
            # --- 타순 검증 보고서 (위원장님 요청 사항) ---
            st.markdown("---")
            st.subheader("📊 타순 순환 배치 검증 보고서")
            order_df = pd.DataFrame(order_stats).T.fillna(0).astype(int)
            order_df.columns = [f"{i}번 타순" for i in order_df.columns]
            
            st.write("**지역별 타순 배정 횟수 (모든 타순에 골고루 배치되었는지 확인)**")
            st.dataframe(order_df, use_container_width=True)
            
            # 누락 검사
            missing = []
            for region, row in order_df.iterrows():
                zeros = [c for c in order_df.columns if row[c] == 0]
                if zeros: missing.append(f"**{region}**: {', '.join(zeros)} 누락")
            
            if not missing: st.success("✅ 검증 완료: 모든 지역 선수가 전 타순을 최소 한 번 이상 경험하도록 배치되었습니다.")
            else: st.warning("⚠️ 일부 지역 인원 부족으로 인해 발생한 타순 누락 내역:\n\n" + "\n".join(missing))

            # 엑셀 다운로드
            print_excel = create_print_excel(res, m_type, h_cnt)
            st.download_button("📥 인쇄용 공식 대진표 다운로드", print_excel, f"{m_type}_최종_대진표.xlsx")

# (채점 로직 생략 - 이전과 동일하게 유지 가능)