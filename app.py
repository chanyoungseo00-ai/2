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
    if num_teams == 0: return pd.DataFrame(), 0
    
    teams = [[] for _ in range(num_teams)]
    
    # 1. 조 편성 (지역 중복 방지)
    if match_type == "개인전":
        players = working_df.to_dict('records')
        r_counts = working_df['지역'].value_counts().to_dict()
        players.sort(key=lambda x: (r_counts.get(x['지역'], 0), x['지역']), reverse=True)
        for p in players:
            best_team = min(teams, key=lambda t: (sum(1 for x in t if x['지역'] == p['지역']), len(t)))
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
                        team.append(females.pop(i)); break
        rem = females + males
        rem_counts = pd.Series([p['지역'] for p in rem]).value_counts().to_dict()
        rem.sort(key=lambda x: (rem_counts.get(x['지역'], 0), x['지역']), reverse=True)
        for p in rem:
            best_team = min(teams, key=lambda t: (sum(1 for x in t if x['지역'] == p['지역']), len(t)))
            best_team.append(p)

    # 2. 타순 평탄화
    for team in teams:
        avail = list(range(1, players_per_team + 1))
        random.shuffle(avail)
        for i, p in enumerate(team): p['타순'] = avail[i]

    # 3. 구장 정렬 (청->백->홍->황)
    final_roster = []
    fields = ['청', '백', '홍', '황']
    for idx, team in enumerate(teams):
        f_idx = idx % 4
        hole = (idx // 4) % holes_per_field + 1
        round_id = (idx // (4 * holes_per_field)) + 1
        s_hole = f"{fields[f_idx]}구장 {hole}홀"
        set_name = f"{round_id}그룹 {fields[f_idx]}구장" if len(teams) > holes_per_field * 4 else f"{fields[f_idx]}구장"
        for p in team:
            final_roster.append({
                '진행 그룹': set_name, '팀': f"{match_type} {idx+1}조", '출발홀': s_hole,
                '타순': p['타순'], '지역': p['지역'], '이름': p['이름'], '성별': p['성별'],
                '_r': round_id, '_f': f_idx, '_h': hole
            })
    res_df = pd.DataFrame(final_roster).sort_values(by=['_r', '_f', '_h', '타순']).reset_index(drop=True)
    return res_df.drop(columns=['_r', '_f', '_h']), num_teams

# ==========================================
# [기능 2] 채점 데이터 정규화 로직
# ==========================================
def load_score_data(file, sheet_name, days):
    df = pd.read_excel(file, sheet_name=sheet_name, skiprows=2, header=None)
    cols = ['일시','조','타순','소속','이름','1_총