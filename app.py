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
    
    # 1. 조 편성 (지역 중복 방지)
    if match_type == "개인전":
        players = working_df.to_dict('records')
        r_counts = working_df['지역'].value_counts().to_dict()
        players.sort(key=lambda x: (r_counts.get(x['지역'], 0), x['지역']), reverse=True)
        for p in players:
            best_team = min(
                teams, 
                key=lambda t: (sum(1 for x in t if x['지역'] == p['지역']), len(t))
            )
            best_team.append(p)
    else: 
        females = working_df[working_df['성별'] == '여'].to_dict('records')
        males = working_df[working_df['성별'] == '남'].to_dict('records')
        for team in teams:
            for _ in range(2):
                if not females: break
                min_overlap = min(sum(1 for x in team if x['지역'] == f['지역']) for f in females)
                for i, f in enumerate(females):
                    if sum(1 for x in team if x['지역'] == f['지역']) == min_overlap:
                        team.append(females.pop(i))
                        break
        rem = females + males
        rem_counts = pd.Series([p['지역'] for p in rem]).value_counts().to_dict()
        rem.sort(key=lambda x: (rem_counts.get(x['지역'], 0), x['지역']), reverse=True)
        for p in rem:
            best_team = min(
                teams, 
                key=lambda t: (sum(1 for x in t if x['지역'] == p['지역']), len(t))
            )
            best_team.append(p)

    # 2. 타순 평탄화
    for team in teams:
        avail = list(range(1, players_per_team + 1))
        random.shuffle(avail)
        for i, p in enumerate(team): 
            p['타순'] = avail[i]

    # 3. 구장 정렬 (청->백->홍->황)
    final_roster = []
    fields = ['청', '백', '홍', '황']
    for idx, team in enumerate(teams):
        f_idx = idx % 4
        hole = (idx // 4) % holes_per_field + 1
        round_id = (idx // (4 * holes_per_field)) + 1
        s_hole = f"{fields[f_idx]}구장 {hole}홀"
        
        if len(teams) > holes_per_field * 4:
            set_name = f"{round_id}그룹 {fields[f_idx]}구장"
        else:
            set_name = f"{fields[f_idx]}구장"
            
        for p in team:
            final_roster.append({
                '진행 그룹': set_name, 
                '팀': f"{match_type} {idx+1}조", 
                '출발홀': s_hole,
                '타순': p['타순'], 
                '지역': p['지역'], 
                '이름': p['이름'], 
                '성별': p['성별'],
                '_r': round_id, 
                '_f': f_idx, 
                '_h': hole
            })
            
    res_df = pd.DataFrame(final_roster).sort_values(
        by=['_r', '_f', '_h', '타순']
    ).reset_index(drop=True)
    
    return res_df.drop(columns=['_r', '_f', '_h']), num_teams

# ==========================================
# [기능 2] 채점 데이터 정규화 로직
# ==========================================
def load_score_data(file, sheet_name, days):
    df = pd.read_excel(file, sheet_name=sheet_name, skiprows=2, header=None)
    
    # 가로 잘림 방지를 위해 세로로 배열
    cols = [
        '일시', '조', '타순', '소속', '이름', 
        '1_총', '1_2', '1_홀', 
        '2_총', '2_2', '2_홀', 
        '3_총', '3_2', '3_홀', 
        '최_총', '최_2', '최_홀'
    ]
    
    if days == "1일차 대회": 
        df = df.iloc[:, :11].copy()
        df.columns = cols[:8] + cols[14:17]
        df['2_총'], df['2_2'], df['2_홀'] = 0, 0, 0
        df['3_총'], df['3_2'], df['3_홀'] = 0, 0, 0
    elif days == "2일차 대회": 
        df = df.iloc[:, :14].copy()
        df.columns = cols[:11] + cols[14:17]
        df['3_총'], df['3_2'], df['3_홀'] = 0, 0, 0
    else: 
        df = df.iloc[:, :17].copy()
        df.columns = cols
    
    df = df.dropna(subset=['이름', '소속'])
    
    num_cols = [
        '1_총', '1_2', '1_홀', 
        '2_총', '2_2', '2_홀', 
        '3_총', '3_2', '3_홀', 
        '최_총', '최_2', '최_홀'
    ]
    for c in num_cols: 
        df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0).astype(int)
        
    return df

# ==========================================
# [메인 UI]
# ==========================================
st.sidebar.title("⛳ 그라운드골프 통합 시스템")
mode = st.sidebar.radio("작업 선택", ["대진표 편성", "대회 채점"])

if mode == "대진표 편성":
    st.title("⛳ 대진표 자동 편성")
    m_type = st.sidebar.radio("편성 부문", ["개인전", "단체전"])
    h_cnt = st.sidebar.radio("출발홀 수", [6, 7, 8], index=2)
    p_cnt = st.sidebar.radio("조당 인원", [6, 7, 8], index=0)
    up_file = st.file_uploader("선수 명단 엑셀 업로드", type=["xlsx"])
    
    if up_file and st.button(f"{m_type} 대진표 생성"):
        df_in = pd.read_excel(up_file)
        df_in.columns = df_in.columns.str.strip()
        
        df_in = df_in.rename(columns={'소속': '지역', '성명': '이름'})
        
        if not {'지역', '이름', '성별'}.issubset(df_in.columns):
            st.error("❌ 엑셀 파일 첫 줄에 [지역], [이름], [성별] 열이 있어야 합니다.")
        else:
            df_in = df_in.dropna(subset=['지역', '이름', '성별']).copy()
            res, t_cnt = assign_teams_and_orders(df_in, h_cnt, p_cnt, m_type)
            st.subheader(f"✅ 편성 완료 (총 {t_cnt}개 조)")
            st.dataframe(res, use_container_width=True)
            
            out = io.BytesIO()
            with pd.ExcelWriter(out, engine='xlsxwriter') as wr: 
                res.to_excel(wr, index=False)
            st.download_button("📥 엑셀 다운로드", out.getvalue(), "대진표.xlsx")

elif mode == "대회 채점":
    st.title("🏆 대회 통합 채점")
    d_set = st.sidebar.radio("대회 일정", ["1일차 대회", "2일차 대회", "3일차 대회"])
    up_score = st.file_uploader("채점표 엑셀 업로드", type=["xlsx"])
    
    if up_score:
        t1, t2 = st.tabs(["🥇 개인전", "🤝 단체전"])
        with t1:
            try:
                df_p = load_score_data(up_score, '개인전 채점표', d_set)
                
                # 강제 합산 로직
                df_p['최_총'] = df_p['1_총'] + df_p['2_총'] + df_p['3_총']
                df_p['최_2'] = df_p['1_2'] + df_p['2_2'] + df_p['3_2']
                df_p['최_홀'] = df_p['1_홀'] + df_p['2_홀'] + df_p['3_홀']
                
                df_p = df_p.sort_values(
                    by=['최_총','최_2','최_홀'], 
                    ascending=[True,False,False]
                ).reset_index(drop=True)
                
                df_p['순위'] = df_p[['최_총','최_2','최_홀']].apply(
                    lambda x: (-x['최_총'], x['최_2'], x['최_홀']), axis=1
                ).rank(method='min', ascending=False).astype(int)
                
                st.subheader(f"🥇 개인전 결과 ({d_set})")
                st.dataframe(
                    df_p[['순위','소속','이름','최_총','최_2','최_홀']], 
                    hide_index=True
                )
            except Exception as e: 
                st.error(f"개인전 시트 오류: {e}")
                
        with t2:
            try:
                df_t = load_score_data(up_score, '단체전 채점표', d_set)
                
                df_t['최_총'] = df_t['1_총'] + df_t['2_총'] + df_t['3_총']
                df_t['최_2'] = df_t['1_2'] + df_t['2_2'] + df_t['3_2']
                df_t['최_홀'] = df_t['1_홀'] + df_t['2_홀'] + df_t['3_홀']
                
                res_t = df_t.groupby('소속', as_index=False)[['최_총','최_2','최_홀']].sum()
                
                res_t = res_t.sort_values(
                    by=['최_총','최_2','최_홀'], 
                    ascending=[True,False,False]
                ).reset_index(drop=True)
                
                res_t['순위'] = res_t[['최_총','최_2','최_홀']].apply(
                    lambda x: (-x['최_총'], x['최_2'], x['최_홀']), axis=1
                ).rank(method='min', ascending=False).astype(int)
                
                st.subheader(f"🤝 단체전 결과 ({d_set})")
                st.dataframe(
                    res_t[['순위','소속','최_총','최_2','최_홀']], 
                    hide_index=True
                )
            except Exception as e: 
                st.error(f"단체전 시트 오류: {e}")