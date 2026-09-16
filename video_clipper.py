import streamlit as st
import pandas as pd
from io import StringIO
import subprocess
from pathlib import Path
import hashlib
import tempfile
import math


# base_dir = Path("C:/temp/clips")
base_dir = Path(tempfile.gettempdir()) / "clips"
base_dir.mkdir(parents=True, exist_ok=True)


def seconds_to_vtt_time(seconds):
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds - int(seconds)) * 1000)
    return f"{hours:02}:{minutes:02}:{secs:02}.{millis:03}"


def create_clip(video_url, start, end, output_file):
    duration = min(60, max(0, end - start))

    cmd = [
        "ffmpeg",
        "-y",
        "-ss",
        str(start),
        "-i",
        video_url,
        "-t",
        str(duration),
        "-avoid_negative_ts",
        "make_zero",
        "-c",
        "copy",
        output_file,
    ]

    subprocess.run(
        cmd,
        check=True,
        capture_output=True,
        text=True,
    )


st.set_page_config(page_title="Video Segment Clipper", layout="wide")

col1, col2, col3 = st.columns([1 / 3, 1 / 3, 1 / 3])

with col1:
    st.header("🎥 Video Segment Clipper")

    video_url = st.text_input(
        "Video URL",
        value="https://test-videos.co.uk/vids/bigbuckbunny/mp4/h264/1080/Big_Buck_Bunny_1080_10s_30MB.mp4",
    )

    if video_url:
        st.video(video_url)

        csv_text = st.text_area(
            "Paste CSV",
            height=200,
            placeholder="""start,end,name,color
3,10,test,green
16,26,test,blue
1000,1026,goal,#28a745""",
        )

        preview_clicked = st.button(
            "Preview",
            type="primary",
            use_container_width=True,
        )

        clip_clicked = st.button(
            "Clip for download",
            use_container_width=True,
        )
    else:
        csv_text = ""
        preview_clicked = False
        clip_clicked = False


# Reserve middle-column layout from top to bottom:
# 1. Header
# 2. Progress / status
# 3. Main content
with col2:
    st.subheader("Generated Clips")
    progress_box = st.empty()
    status_box = st.empty()
    middle_content = st.container()

with col3:
    with st.expander("Manual / How to use"):
        st.markdown(
            """
            ### Video Segment Clipper
    
            This app lets you preview or create short video clips from a video URL using pasted CSV or tab-separated data.
    
            #### How to use
    
            1. Enter or paste a **Video URL**.
               - After changing the URL, press **Enter**.
    
            2. Paste your clip table into **Paste CSV**.
               - Supported formats:
                 - comma-separated
                 - tab-separated
               - Required columns:
                 - `start`
                 - `end`
                 - `name`
    
            3. After editing the large text box, press **Ctrl+Enter**.
               - This ensures Streamlit applies the latest text.
    
            4. Click:
               - **Preview** to preview clips
               - **Clip to download** to generate downloadable MP4 files
    
            #### Notes
    
            - `start` values are rounded **down**
            - `end` values are rounded **up**
            - Clips are limited to **60 seconds**
            """
        )
    right_content = st.container()


if preview_clicked or clip_clicked:
    try:
        csv_text = csv_text.replace("\u200b", "")
        
        sample = csv_text.splitlines()[0] if csv_text else ""
        delimiter = "\t" if "\t" in sample else ","
        
        df = pd.read_csv(
            StringIO(csv_text),
            sep=delimiter,
        )
        
        df.columns = (
            df.columns.astype(str)
            .str.strip()
            .str.replace("\u200b", "", regex=False)
            .str.replace("\ufeff", "", regex=False)
        )
        


        required_columns = {"start", "end", "name"}
        missing = required_columns - set(df.columns)

        if missing:
            st.error(f"Missing columns: {', '.join(sorted(missing))}")

        elif df.empty:
            st.warning("The CSV contains no rows.")

        else:
            df["start"] = pd.to_numeric(df["start"], errors="raise").apply(math.floor)
            df["end"] = pd.to_numeric(df["end"], errors="raise").apply(math.ceil)
            downloads = []
            total_rows = len(df)

            if clip_clicked:
                progress_bar = progress_box.progress(0, text="Preparing clips...")
            else:
                progress_bar = None

            for idx, row in df.iterrows():
                target_container = middle_content if idx % 2 == 0 else right_content

                start = float(row["start"])
                eind = float(row["end"])
                clip_name = f"{str(row['name']).upper()}_{idx + 1:02d}"

                if eind <= start:
                    status_box.warning(
                        f"Skipping '{clip_name}': end must be greater than start."
                    )
                    continue

                if clip_clicked and progress_bar is not None:
                    percent_before = int((idx / total_rows) * 100)
                    progress_bar.progress(
                        percent_before,
                        text=f"Clipping {idx + 1}/{total_rows}: {clip_name}",
                    )
                    status_box.info(
                        f"Processing clip {idx + 1} of {total_rows}: {clip_name}"
                    )

                with target_container:
                    if clip_clicked:
                        video_dir = (
                            base_dir
                            / hashlib.sha1(video_url.encode()).hexdigest()[:8]
                        )
                        video_dir.mkdir(parents=True, exist_ok=True)

                        output_file = video_dir / f"{clip_name}.mp4"

                        create_clip(
                            str(video_url),
                            start,
                            eind,
                            str(output_file),
                        )

                        downloads.append(
                            {
                                "name": clip_name,
                                "file": output_file,
                            }
                        )
                    else:
                        subtitle_content = f"""WEBVTT

{seconds_to_vtt_time(start)} --> {seconds_to_vtt_time(eind)} line:10% position:90% align:end
<b>{clip_name}</b>
"""

                        st.video(
                            video_url,
                            start_time=start,
                            end_time=eind,
                            subtitles=subtitle_content,
                        )

                if clip_clicked and progress_bar is not None:
                    percent_after = int(((idx + 1) / total_rows) * 100)
                    progress_bar.progress(
                        percent_after,
                        text=f"Done {idx + 1}/{total_rows}: {clip_name}",
                    )

            if clip_clicked and progress_bar is not None:
                progress_bar.progress(100, text="All clips completed")
                status_box.success(f"Finished generating {len(downloads)} clip(s).")

                with middle_content:
                    dl_col1, dl_col2 = st.columns(2)

                    for idx, item in enumerate(downloads):
                        target_dl_col = dl_col1 if idx % 2 == 0 else dl_col2

                        with target_dl_col:
                            with open(item["file"], "rb") as f:
                                st.download_button(
                                    label=f"📥 {item['name']}",
                                    data=f.read(),
                                    file_name=f"{item['name']}.mp4",
                                    mime="video/mp4",
                                    key=f"download_{item['name']}",
                                    on_click="ignore",
                                    width="stretch",
                                )

    except Exception as e:
        st.error(f"Failed to parse CSV: {e}")
