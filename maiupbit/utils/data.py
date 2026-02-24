"""데이터 준비 유틸리티 모듈.

OHLCV DataFrame에 지표/시그널을 추가하고 JSON으로 직렬화하는
함수와, 지시 파일 읽기 함수를 제공합니다.
"""

import json
import logging
from typing import Optional

import pandas as pd

from maiupbit.indicators.signals import add_all_signals

logger = logging.getLogger(__name__)


def prepare_data(df_daily: pd.DataFrame, df_hourly: pd.DataFrame) -> str:
    """일별/시간별 DataFrame에 지표와 시그널을 추가한 뒤 JSON 문자열로 반환합니다.

    처리 흐름:
        1. 일별 데이터에 기술 지표 + 시그널 컬럼 추가
        2. 시간별 데이터에 기술 지표 + 시그널 컬럼 추가
        3. 두 DataFrame을 'daily'/'hourly' 키로 합쳐 JSON 직렬화

    Args:
        df_daily: 일별 OHLCV DataFrame.
        df_hourly: 시간별 OHLCV DataFrame.

    Returns:
        combined DataFrame의 JSON 문자열 (orient='split').
        분석 엔진(GPT-4 등)에 그대로 전달할 수 있습니다.
    """
    df_daily = add_all_signals(df_daily)
    df_hourly = add_all_signals(df_hourly)

    combined_df = pd.concat([df_daily, df_hourly], keys=["daily", "hourly"])
    return json.dumps(combined_df.to_json(orient="split"))


def get_instructions(file_path: str) -> Optional[str]:
    """파일에서 분석 지시사항(시스템 프롬프트)을 읽어 반환합니다.

    Args:
        file_path: 지시사항 파일 경로 (UTF-8 인코딩 텍스트 파일).

    Returns:
        파일 내용 문자열. 파일을 찾지 못하거나 읽기 오류 시 None 반환.
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        logger.error("파일을 찾을 수 없습니다: %s", file_path)
    except IOError as exc:
        logger.error("파일 읽기 오류: %s", exc)
    return None
