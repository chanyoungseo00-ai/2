import streamlit as st
import pandas as pd
import numpy as np
import io

st.set_page_config(page_title="그라운드골프 대회 자동 채점 시스템", layout="wide")

st.title("🏆 개인전 및 단체전 자동 채점 시스템")
st.markdown("채점표 엑셀 파일을 업로드하면 **개인전**과 **단체전** 순위표 및 시상자 명단을 한 번에 자동 생성합니다.")

st.info("""
**💡 순위 결정 규정 (개인/단체 공통)**
1. **총타수**가 가장 적은 선수(또는 팀)
2. 동타일 경우, **2타수**가 많은 선수(또는 팀)
3. 2타수도 같을 경우, **홀인원** 개수가 많은 선수(또는 팀)
""")

uploaded_file = st.file_uploader("채점표 엑셀 파일을 업로드해주세요 (.xlsx)", type=["xlsx"])

if uploaded_file is not None:
    # 화면을 개인전과 단체전 탭으로 분리
    tab1, tab2 = st.tabs(["🥇 개인전 결과", "🤝 단체전 결과"])
    
    # 엑셀 공통 컬럼 설정 (왼쪽 1~14열 개별 선수 데이터만 추출)
    col_names = [
        '일시', '조', '타순', '소속', '성명', 
        '1일차_총타수', '1일차_2타수', '1일차_홀인원', 
        '2일차_총타수', '2일차_2타수', '2일차_홀인원', 
        '최종_총타수', '최종_2타수', '최종_홀인원'
    ]

    try:
        with st.spinner("순위를 계산하고 시상표를 작성 중입니다..."):
            
            # ==========================================
            # 1. 개인전 데이터 처리
            # ==========================================
            df_ind = pd.read_excel(uploaded_file, sheet_name='개인전 채점표', skiprows=2, usecols=range(14), names=col_names)
            df_ind = df_ind.dropna(subset=['성명', '소속'])
            
            score_cols = ['최종_총타수', '최종_2타수', '최종_홀인원']
            for col in score_cols:
                df_ind[col] = pd.to_numeric(df_ind[col], errors='coerce').fillna(0).astype(int)
                
            df_ind['최종_총타수'] = np.where(df_ind['최종_총타수'] == 0, pd.to_numeric(df_ind['1일차_총타수'], errors='coerce').fillna(0) + pd.to_numeric(df_ind['2일차_총타수'], errors='coerce').fillna(0), df_ind['최종_총타수'])
            df_ind['최종_2타수'] = np.where(df_ind['최종_총타수'] > 0, pd.to_numeric(df_ind['1일차_2타수'], errors='coerce').fillna(0) + pd.to_numeric(df_ind['2일차_2타수'], errors='coerce').fillna(0), df_ind['최종_2타수'])
            df_ind['최종_홀인원'] = np.where(df_ind['최종_총타수'] > 0, pd.to_numeric(df_ind['1일차_홀인원'], errors='coerce').fillna(0) + pd.to_numeric(df_ind['2일차_홀인원'], errors='coerce').fillna(0), df_ind['최종_홀인원'])

            df_ind = df_ind[df_ind['최종_총타수'] > 0].copy()

            # 개인전 순위 산정
            df_ind = df_ind.sort_values(by=['최종_총타수', '최종_2타수', '최종_홀인원'], ascending=[True, False, False]).reset_index(drop=True)
            df_ind['순위'] = df_ind[['최종_총타수', '최종_2타수', '최종_홀인원']].apply(
                lambda x: (-x['최종_총타수'], x['최종_2타수'], x['최종_홀인원']), axis=1
            ).rank(method='min', ascending=False).astype(int)

            ind_ranking = df_ind[['순위', '소속', '성명', '최종_총타수', '최종_2타수', '최종_홀인원']].copy()
            ind_ranking.columns = ['순위', '소속', '성명', '총타수', '2타수', '홀인원']

            # 개인전 시상자 명단 (5위까지 + 장려상 5명)
            ind_awards_data = []
            award_titles = ['1위', '2위', '3위', '4위', '5위'] + ['장려상'] * 5
            for i, title in enumerate(award_titles):
                if i < len(ind_ranking):
                    p = ind_ranking.iloc[i]
                    ind_awards_data.append([title, p['소속'], p['성명'], p['총타수'], p['2타수'], p['홀인원']])
                else:
                    ind_awards_data.append([title, '', '', '', '', ''])
            ind_awards = pd.DataFrame(ind_awards_data, columns=['구분', '소속', '성명', '총타수', '2타수', '홀인원'])


            # ==========================================
            # 2. 단체전 데이터 처리
            # ==========================================
            df_team_raw = pd.read_excel(uploaded_file, sheet_name='단체전 채점표', skiprows=2, usecols=range(14), names=col_names)
            df_team_raw = df_team_raw.dropna(subset=['성명', '소속'])
            
            for col in score_cols:
                df_team_raw[col] = pd.to_numeric(df_team_raw[col], errors='coerce').fillna(0).astype(int)
                
            df_team_raw['최종_총타수'] = np.where(df_team_raw['최종_총타수'] == 0, pd.to_numeric(df_team_raw['1일차_총타수'], errors='coerce').fillna(0) + pd.to_numeric(df_team_raw['2일차_총타수'], errors='coerce').fillna(0), df_team_raw['최종_총타수'])
            df_team_raw['최종_2타수'] = np.where(df_team_raw['최종_총타수'] > 0, pd.to_numeric(df_team_raw['1일차_2타수'], errors='coerce').fillna(0) + pd.to_numeric(df_team_raw['2일차_2타수'], errors='coerce').fillna(0), df_team_raw['최종_2타수'])
            df_team_raw['최종_홀인원'] = np.where(df_team_raw['최종_총타수'] > 0, pd.to_numeric(df_team_raw['1일차_홀인원'], errors='coerce').fillna(0) + pd.to_numeric(df_team_raw['2일차_홀인원'], errors='coerce').fillna(0), df_team_raw['최종_홀인원'])

            df_team_raw = df_team_raw[df_team_raw['최종_총타수'] > 0].copy()

            # ★ 단체전 핵심: 소속(팀)별로 점수 합산하기 ★
            df_team = df_team_raw.groupby('소속', as_index=False)[['최종_총타수', '최종_2타수', '최종_홀인원']].sum()

            # 단체전 순위 산정
            df_team = df_team.sort_values(by=['최종_총타수', '최종_2타수', '최종_홀인원'], ascending=[True, False, False]).reset_index(drop=True)
            df_team['순위'] = df_team[['최종_총타수', '최종_2타수', '최종_홀인원']].apply(
                lambda x: (-x['최종_총타수'], x['최종_2타수'], x['최종_홀인원']), axis=1
            ).rank(method='min', ascending=False).astype(int)

            team_ranking = df_team[['순위', '소속', '최종_총타수', '최종_2타수', '최종_홀인원']].copy()
            team_ranking.columns = ['순위', '소속', '총타수', '2타수', '홀인원']

            # 단체전 시상자 명단 (1위~5위, 장려상 5팀 등 필요한 만큼 출력)
            team_awards_data = []
            for i, title in enumerate(award_titles):
                if i < len(team_ranking):
                    t = team_ranking.iloc[i]
                    team_awards_data.append([title, t['소속'], t['총타수'], t['2타수'], t['홀인원']])
                else:
                    team_awards_data.append([title, '', '', '', ''])
            team_awards = pd.DataFrame(team_awards_data, columns=['구분', '소속', '총타수', '2타수', '홀인원'])


            # ==========================================
            # 3. 화면 출력 및 다운로드 파일 생성
            # ==========================================
            with tab1:
                st.subheader("🥇 개인전 결과")
                col1, col2 = st.columns([1, 1])
                with col1:
                    st.markdown("**개인전 시상 명단**")
                    st.dataframe(ind_awards, use_container_width=True, hide_index=True)
                with col2:
                    st.markdown("**개인전 전체 순위표**")
                    st.dataframe(ind_ranking, use_container_width=True, hide_index=True)

            with tab2:
                st.subheader("🤝 단체전 결과")
                col3, col4 = st.columns([1, 1])
                with col3:
                    st.markdown("**단체전 시상 명단**")
                    st.dataframe(team_awards, use_container_width=True, hide_index=True)
                with col4:
                    st.markdown("**단체전 전체 순위표**")
                    st.dataframe(team_ranking, use_container_width=True, hide_index=True)

            # 모든 결과를 하나의 엑셀 파일로 통합 저장
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                ind_ranking.to_excel(writer, index=False, sheet_name='개인전 순위표')
                ind_awards.to_excel(writer, index=False, sheet_name='개인전 시상(출력물)')
                team_ranking.to_excel(writer, index=False, sheet_name='단체전 순위표')
                team_awards.to_excel(writer, index=False, sheet_name='단체전 시상(출력물)')
                
            processed_data = output.getvalue()
            
            st.success("🎉 개인전 및 단체전 채점이 모두 완료되었습니다! 아래 버튼을 눌러 통합 엑셀을 다운로드하세요.")
            st.download_button(
                label="📥 최종 통합 결과(개인/단체) 엑셀 다운로드",
                data=processed_data,
                file_name="제18회_대한체육회장배_최종결과.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            
    except ValueError as ve:
        st.error(f"엑셀 파일 구조 오류: 업로드하신 파일에 '개인전 채점표'와 '단체전 채점표' 시트가 모두 있는지 확인해주세요. ({ve})")
    except Exception as e:
        st.error(f"오류가 발생했습니다. 파일 형식을 다시 확인해주세요: {e}")