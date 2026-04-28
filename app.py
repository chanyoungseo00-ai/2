import streamlit as st
import pandas as pd
import numpy as np
import io
import random
import itertools

# 화면 기본 설정 (반드시 맨 위에 위치)
st.set_page_config(page_title="그라운드골프 통합 운영 시스템", layout="wide")

# =====================================================================
# [함수 1] 대진표 자동 편성 로직
# =====================================================================
def assign_teams_and_orders(df, holes_per_field=8, players_per_team=6, match_type="개인전"):
    working_df = df.copy()
    total_players = len(working_df)
    team_size = players_per_team
    num_teams = (total_players + team_size - 1) // team_size
    
    if num_teams == 0:
        return pd.DataFrame(), 0

    teams = [[] for _ in range(num_teams)]

    # 1. 조 편성 (지역 중복 방지)
    if match_type == "개인전":
        players = working_df.to_dict('records')
        region_counts = working_df['지역'].value_counts().to_dict()
        players.sort(key=lambda x: (region_counts.get(x['지역'], 0), x['지역']), reverse=True)
        
        for p in players:
            best_team = min(
                teams, 
                key=lambda t: (sum(1 for x in t if x['지역'] == p['지역']), len(t))
            )
            best_team.append(p)
    else: 
        females = working_df[working_df['성별'] == '여'].to_dict('records')
        males = working_df[working_df['성별'] == '남'].to_dict('records')
        
        f_counts = pd.Series([p['지역'] for p in females]).value_counts().to_dict()
        females.sort(key=lambda x: (f_counts.get(x['지역'], 0), x['지역']), reverse=True)
        
        for team in teams:
            for _ in range(2):
                if not females: 
                    break
                min_overlap = min(sum(1 for x in team if x['지역'] == f['지역']) for f in females)
                for i, f in enumerate(females):
                    if sum(1 for x in team if x['지역'] == f['지역']) == min_overlap:
                        team.append(females.pop(i))
                        break
                        
        remaining = females + males
        rem_counts = pd.Series([p['지역'] for p in remaining]).value_counts().to_dict()
        remaining.sort(key=lambda x: (rem_counts.get(x['지역'], 0), x['지역']), reverse=True)
        
        for p in remaining:
            best_team = min(
                teams, 
                key=lambda t: (sum(1 for x in t if x['지역'] == p['지역']), len(t))
            )
            best_team.append(p)

    # 2. 타순 평탄화 로직
    region_order_count = {r: {i: 0 for i in range(1, players_per_team + 1)} for r in working_df['지역'].unique()}
    
    for team in teams:
        available_orders = list(range(1, players_per_team + 1))
        best_perm = None
        best_score = float('inf')
        
        if len(available_orders) <= 6:
            perms = list(itertools.permutations(available_orders, len(team)))
        else:
            perms = [random.sample(available_orders, len(team)) for _ in range(2000)]
            
        for perm in perms:
            score = 0
            for i, p in enumerate(team):
                count = region_order_count[p['지역']].get(perm[i], 0)
                score += count ** 2 
            if score < best_score:
                best_score = score
                best_perm = perm
                if score == 0: 
                    break 
                
        for i, p in enumerate(team):
            p['타순'] = best_perm[i]
            region_order_count[p['지역']][best_perm[i]] += 1

    for _ in range(3000):
        usage = {r: {i: 0 for i in range(1, players_per_team + 1)} for r in working_df['지역'].unique()}
        for team in teams:
            for p in team: 
                usage[p['지역']][p['타순']] += 1
                
        worst_region, worst_skew, worst_over, worst_under = None, -1, -1, -1
        for r, u in usage.items():
            skew = max(u.values()) - min(u.values())
            if skew > worst_skew:
                worst_skew = skew
                worst_region = r
                worst_over = max(u, key=u.get)
                worst_under = min(u, key=u.get)
                
        if worst_skew <= 1: 
            break 
        
        teams_with_over = [t for t in teams if any(p['지역'] == worst_region and p['타순'] == worst_over for p in t)]
        swapped = False
        random.shuffle(teams_with_over)
        
        for team in teams_with_over:
            p1 = next((p for p in team if p['지역'] == worst_region and p['타순'] == worst_over), None)
            p2 = next((p for p in team if p['타순'] == worst_under), None)
            if p1 and p2:
                r2 = p2['지역']
                if usage[r2][worst_over] <= usage[r2][worst_under]: 
                    p1['타순'], p2['타순'] = p2['타순'], p1['타순']
                    swapped = True
                    break
            elif p1 and not p2:
                p1['타순'] = worst_under
                swapped = True
                break
                
        if not swapped and teams_with_over:
            team = teams_with_over[0]
            p1 = next((p for p in team if p['지역'] == worst_region and p['타순'] == worst_over), None)
            p2 = next((p for p in team if p['타순'] == worst_under), None)
            if p1 and p2: 
                p1['타순'], p2['타순'] = p2['타순'], p1['타순']
            elif p1: 
                p1['타순'] = worst_under

    # 3. 구장 배정 및 정렬 (청 ➔ 백 ➔ 홍 ➔ 황)
    final_roster = []
    fields = ['청', '백', '홍', '황']
    
    for team_idx, team in enumerate(teams):
        team_id = team_idx + 1
        field_val = team_idx % 4
        field = fields[field_val]
        hole = (team_idx // 4) % holes_per_field + 1
        round_id = (team_idx // (4 * holes_per_field)) + 1 
        start_hole = f"{field}구장 {hole}홀"
        
        set_name = f"{round_id}그룹 {field}구장" if len(teams) > holes_per_field * 4 else f"{field}구장"
            
        for p in team:
            final_roster.append({
                '진행 그룹': set_name, '팀': f"{match_type} {team_id}조", '출발홀': start_hole, 
                '타순': p['타순'], '지역': p['지역'], '이름': p['이름'], '성별': p['성별'],
                '_round_val': round_id, '_field_val': field_val, '_hole_val': hole
            })
            
    final_df = pd.DataFrame(final_roster)
    final_df = final_df.sort_values(
        by=['_round_val', '_field_val', '_hole_val', '타순']
    ).reset_index(drop=True)
    final_df = final_df.drop(columns=['_round_val', '_field_val', '_hole_val'])
    
    return final_df, num_teams


# =====================================================================
# [함수 2] 채점 데이터 로드 및 정규화 로직
# =====================================================================
def load_and_standardize_data(file, sheet_name, days_setting):
    df = pd.read_excel(file, sheet_name=sheet_name, skiprows=2, header=None)
    
    if days_setting == "3일차 대회":
        df = df.iloc[:, :17].copy()
        df.columns = [
            '일시', '조', '타순', '소속', '이름', 
            '1일차_총타수', '1일차_2타수', '1일차_홀인원', 
            '2일차_총타수', '2일차_2타수', '2일차_홀인원', 
            '3일차_총타수', '3일차_2타수', '3일차_홀인원', 
            '최종_총타수', '최종_2타수', '최종_홀인원'
        ]
    elif days_setting == "2일차 대회":
        df = df.iloc[:, :14].copy()
        df.columns = [
            '일시', '조', '타순', '소속', '이름', 
            '1일차_총타수', '1일차_2타수', '1일차_홀인원', 
            '2일차_총타수', '2일차_2타수', '2일차_홀인원', 
            '최종_총타수', '최종_2타수', '최종_홀인원'
        ]
        df['3일차_총타수'], df['3일차_2타수'], df['3일차_홀인원'] = 0, 0, 0
    else: 
        df = df.iloc[:, :11].copy()
        df.columns = [
            '일시', '조', '타순', '소속', '이름', 
            '1일차_총타수', '1일차_2타수', '1일차_홀인원', 
            '최종_총타수', '최종_2타수', '최종_홀인원'
        ]
        df['2일차_총타수'], df['2일차_2타수'], df['2일차_홀인원'] = 0, 0, 0
        df['3일차_총타수'], df['3일차_2타수'], df['3일차_홀인원'] = 0, 0, 0
        
    df = df.dropna(subset=['이름', '소속'])
    
    num_cols = [
        '1일차_총타수', '1일차_2타수', '1일차_홀인원', 
        '2일차_총타수', '2일차_2타수', '2일차_홀인원', 
        '3일차_총타수', '3일차_2타수', '3일차_홀인원', 
        '최종_총타수', '최종_2타수', '최종_홀인원'
    ]
    for col in num_cols:
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype(int)
        
    return df


# =====================================================================
# [메인 화면] 사이드바 메뉴 및 UI 구성
# =====================================================================
st.sidebar.title("⛳ 운영 시스템 메뉴")
app_mode = st.sidebar.radio("▶ 작업을 선택하세요", ["1. 대진표 자동 편성", "2. 대회 통합 채점"])
st.sidebar.markdown("---")

# ---------------------------------------------------------------------
# 화면 A: 대진표 편성 시스템
# ---------------------------------------------------------------------
if app_mode == "1. 대진표 자동 편성":
    st.title("⛳ 그라운드골프 대진표 자동 편성 시스템")
    
    with st.sidebar:
        st