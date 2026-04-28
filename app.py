import streamlit as st
import pandas as pd
import numpy as np
import io
import random
import itertools

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
                        team.append(females.pop(i))
                        break
        rem = females + males
        rem_counts = pd.Series([p['지역'] for p in rem]).value_counts().to_dict()
        rem.sort(key=lambda x: (rem_counts.get(x['지역'], 0), x['지역']), reverse=True)
        for p in rem:
            best_team = min(teams, key=lambda t: (sum(1 for x in t if x['지역'] == p['지역']), len(t)))
            best_team.append(p)

    for team in teams:
        avail = list(range(1, players_per_team + 1))
        random.shuffle(avail)
        for i, p in enumerate(team): 
            p['타순'] = avail[i]

    final_roster = []
    fields = ['청', '백', '홍', '황']
    for idx, team in enumerate(teams):
        f_idx = idx % 4
        hole = (idx // 4) % holes_per_field + 1
        round_id = (idx // (4 * holes_per_field)) + 1
        
        if len(teams) > holes_per_field * 4:
            set_name = f"{round_id}그룹 {fields[f_idx]}구장"
        else:
            set_name = f"{fields[f_idx]}구장"
            
        for p in team:
            final_roster.append({
                '진행 그룹': set_name, 
                '팀': f"{match_type} {idx+1}조", 
                '구장': f"{fields[f_idx]}구장",
                '홀': hole,
                '타순': p['타순'], 
                '지역': p['지역'], 
                '이름': p['이름'], 
                '성별': p['성별']
            })
            
    res_df = pd.DataFrame(final_roster).sort_values(
        by=['진행 그룹', '구장', '홀', '타순']
    ).reset_index(drop=True)
    
    return res_df, num_teams


# ==========================================
# [기능 1-2] 인쇄용 엑셀 출력 포맷터 (핵심 업그레이드)
# ==========================================
def create_formatted_excel(df, match_type, holes_per_field):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        workbook = writer.book
        
        # 디자인 포맷 설정 (원본 양식과 동일하게 구현)
        title_fmt = workbook.add_format({'bold': True, 'font_size': 14})
        subtitle_fmt = workbook.add_format({'font_size': 11})
        header_fmt = workbook.add_format({'bold': True, 'bg_color': '#EFEFEF', 'border': 1, 'align': 'center', 'valign': 'vcenter'})
        cell_fmt = workbook.add_format({'border': 1, 'align': 'center', 'valign': 'vcenter'})
        
        groups = df['진행 그룹'].unique()
        
        for group in groups:
            group_df = df[df['진행 그룹'] == group]
            sheet_name = str(group)[:31] # 엑셀 시트 이름
            worksheet = workbook.add_worksheet(sheet_name)
            
            # 셀 너비 설정 (인쇄 시 잘림 방지)
            worksheet.set_column(0, 0, 2)   # 여백
            worksheet.set_column(1, 1, 8)   # 출발홀
            worksheet.set_column(2, 2, 6)   # 타순
            worksheet.set_column(3, 3, 12)  # 소속
            worksheet.set_column(4, 4, 10)  # 성명
            worksheet.set_column(5, 5, 6)   # 성별
            worksheet.set_column(6, 6, 12)  # 심판 (빈칸용)
            worksheet.set_column(7, 7, 2)   # 가운데 여백
            worksheet.set_column(8, 8, 8)   # 출발홀
            worksheet.set_column(9, 9, 6)   # 타순
            worksheet.set_column(10, 10, 12)# 소속
            worksheet.set_column(11, 11, 10)# 성명
            worksheet.set_column(12, 12, 6) # 성별
            worksheet.set_column(13, 13, 12)# 심판 (빈칸용)

            # 상단 제목 작성
            worksheet.write(0, 1, f"{match_type} 대진표", title_fmt)
            worksheet.write(2, 1, f"{group} 경기 (시간을 직접 입력하세요)", subtitle_fmt)
            
            row = 4
            headers = ['출발홀', '타순', '소 속', '성 명', '성별', '심 판']
            
            # 1&2홀, 3&4홀씩 짝지어서 2열 레이아웃으로 출력
            for h in range(1, holes_per_field + 1, 2):
                # 헤더(제목줄) 출력
                for col_num, head in enumerate(headers):
                    worksheet.write(row, col_num + 1, head, header_fmt)
                    if h + 1 <= holes_per_field:
                        worksheet.write(row, col_num + 8, head, header_fmt)
                row += 1
                
                # 왼쪽 홀(h) 데이터
                left_data = group_df[group_df['홀'] == h]
                # 오른쪽 홀(h+1) 데이터
                right_data = group_df[group_df['홀'] == h + 1] if h + 1 <= holes_per_field else pd.DataFrame()
                
                max_rows = max(len(left_data), len(right_data))
                
                for i in range(max_rows):
                    # 왼쪽 영역 쓰기
                    if i < len(left_data):
                        p = left_data.iloc[i]
                        worksheet.write(row + i, 1, str(h) if i == 0 else "", cell_fmt)
                        worksheet.write(row + i, 2, p['타순'], cell_fmt)
                        worksheet.write(row + i, 3, p['지역'], cell_fmt)
                        worksheet.write(row + i, 4, p['이름'], cell_fmt)
                        worksheet.write(row + i, 5, p['성별'], cell_fmt)
                        worksheet.write(row + i, 6, "", cell_fmt) # 심판 빈칸
                    else:
                        for c in range(1, 7): worksheet.write(row + i, c, "", cell_fmt)
                        
                    # 오른쪽 영역 쓰기
                    if i < len(right_data):
                        p = right_data.iloc[i]
                        worksheet.write(row + i, 8, str(h+1) if i == 0 else "", cell_fmt)
                        worksheet.write(row + i, 9, p['타순'], cell_fmt)
                        worksheet.write(row + i, 10, p['지역'], cell_fmt)
                        worksheet.write(row + i, 11, p['이름'], cell_fmt)
                        worksheet.write(row + i, 12, p['성별'], cell_fmt)
                        worksheet.write(row + i, 13, "", cell_fmt) # 심판 빈칸
                    elif h + 1 <= holes_per_field:
                        for c in range(8, 14): worksheet.write(row + i, c, "", cell_fmt)
                        
                row += max_rows + 1 # 다음 홀 그룹과의 간격
        
        # 관리자용 데이터베이스 시트 별도 추가
        df.to_excel(writer, index=False, sheet_name='관리용_데이터원본')
        
    return output.getvalue()


# ==========================================
# [기능 2] 채점 데이터 로드
# ==========================================
def load_score_data(file, sheet_name, days):
    df = pd.read_excel(file, sheet_name=sheet_name, skiprows=2, header=None)
    cols = ['일시', '조', '타순', '소속', '이름', '1_총', '1_2', '1_홀', '2_총', '2_2', '2_홀', '3_총', '3_2', '3_홀', '최_총', '최_2', '최_홀']
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
    num_cols = ['1_총', '1_2', '1_홀', '2_총', '2_2', '2_홀', '3_총', '3_2', '3_홀', '최_총', '최_2', '최_홀']
    for c in num_cols: df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0).astype(int)
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
        if '이름' not in df_in.columns and '성명' not in df_in.columns:
            df_in = pd.read_excel(up_file, skiprows=1)
            
        df_in.columns = df_in.columns.astype(str).str.strip()
        df_in = df_in.rename(columns={'소속': '지역', '성명': '이름'})
        
        if not {'지역', '이름', '성별'}.issubset(df_in.columns):
            st.error("❌ 엑셀 파일에 [지역], [이름], [성별] 열을 찾을 수 없습니다.")
        else:
            df_in = df_in.dropna(subset=['지역', '이름', '성별'])[['지역', '이름', '성별']].copy()
            res, t_cnt = assign_teams_and_orders(df_in, h_cnt, p_cnt, m_type)
            
            st.subheader(f"✅ 편성 완료 (총 {t_cnt}개 조)")
            st.caption("아래 표는 데이터 구조이며, 엑셀을 다운로드하시면 공식 인쇄용 양식(2단 레이아웃, 심판란 포함)으로 자동 생성됩니다.")
            st.dataframe(res, use_container_width=True)
            
            # 여기서 인쇄용 엑셀 포맷 생성기를 호출
            formatted_excel_data = create_formatted_excel(res, m_type, h_cnt)
            
            st.download_button(
                label="📥 인쇄용 공식 대진표 엑셀 다운로드", 
                data=formatted_excel_data, 
                file_name=f"{m_type}_대진표(출력용).xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

elif mode == "대회 채점":
    st.title("🏆 대회 통합 채점")
    d_set = st.sidebar.radio("대회 일정", ["1일차 대회", "2일차 대회", "3일차 대회"])
    up_score = st.file_uploader("채점표 엑셀 업로드", type=["xlsx"])
    
    if up_score:
        t1, t2 = st.tabs(["🥇 개인전", "🤝 단체전"])
        with t1:
            try:
                df_p = load_score_data(up_score, '개인전 채점표', d_set)
                df_p['최_총'] = df_p['1_총'] + df_p['2_총'] + df_p['3_총']
                df_p['최_2'] = df_p['1_2'] + df_p['2_2'] + df_p['3_2']
                df_p['최_홀'] = df_p['1_홀'] + df_p['2_홀'] + df_p['3_홀']
                df_p = df_p.sort_values(['최_총','최_2','최_홀'], ascending=[True,False,False]).reset_index(drop=True)
                df_p['순위'] = df_p[['최_총','최_2','최_홀']].apply(lambda x:(-x[0],x[1],x[2]), axis=1).rank(method='min', ascending=False).astype(int)
                st.dataframe(df_p[['순위','소속','이름','최_총','최_2','최_홀']], hide_index=True)
            except Exception as e: st.error(f"개인전 시트 오류: {e}")
                
        with t2:
            try:
                df_t = load_score_data(up_score, '단체전 채점표', d_set)
                df_t['최_총'] = df_t['1_총'] + df_t['2_총'] + df_t['3_총']
                df_t['최_2'] = df_t['1_2'] + df_t['2_2'] + df_t['3_2']
                df_t['최_홀'] = df_t['1_홀'] + df_t['2_홀'] + df_t['3_홀']
                res_t = df_t.groupby('소속', as_index=False)[['최_총','최_2','최_홀']].sum()
                res_t = res_t.sort_values(['최_총','최_2','최_홀'], ascending=[True,False,False]).reset_index(drop=True)
                res_t['순위'] = res_t[['최_총','최_2','최_홀']].apply(lambda x:(-x[0],x[1],x[2]), axis=1).rank(method='min', ascending=False).astype(int)
                st.dataframe(res_t[['순위','소속','최_총','최_2','최_홀']], hide_index=True)
            except Exception as e: st.error(f"단체전 시트 오류: {e}")