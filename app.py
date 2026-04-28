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
        return pd.DataFrame(), 0, {}
    
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
        # 단체전: 모든 조에 여자 선수 2명 이상 필수 포함
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