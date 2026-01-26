from dotenv import load_dotenv
from openai import OpenAI
import json
import os
import requests
from pypdf import PdfReader
import gradio as gr


load_dotenv("../.env", override=True)

def push(text):
    requests.post(
        "https://api.pushover.net/1/messages.json",
        data={
            "token": os.getenv("PUSHOVER_TOKEN"),
            "user": os.getenv("PUSHOVER_USER"),
            "message": text,
        }
    )


def record_user_details(email, name="Name not provided", notes="not provided"):
    push(f"Recording {name} with email {email} and notes {notes}")
    return {"recorded": "ok"}

def record_unknown_question(question):
    push(f"Recording {question}")
    return {"recorded": "ok"}

record_user_details_json = {
    "name": "record_user_details",
    "description": "Use this tool to record that a user is interested in being in touch and provided an email address",
    "parameters": {
        "type": "object",
        "properties": {
            "email": {
                "type": "string",
                "description": "The email address of this user"
            },
            "name": {
                "type": "string",
                "description": "The user's name, if they provided it"
            }
            ,
            "notes": {
                "type": "string",
                "description": "Any additional information about the conversation that's worth recording to give context"
            }
        },
        "required": ["email"],
        "additionalProperties": False
    }
}

record_unknown_question_json = {
    "name": "record_unknown_question",
    "description": "Always use this tool to record any question that couldn't be answered as you didn't know the answer",
    "parameters": {
        "type": "object",
        "properties": {
            "question": {
                "type": "string",
                "description": "The question that couldn't be answered"
            },
        },
        "required": ["question"],
        "additionalProperties": False
    }
}

tools = [{"type": "function", "function": record_user_details_json},
        {"type": "function", "function": record_unknown_question_json}]


class Me:

    def __init__(self):
        self.openai = OpenAI(timeout=60.0)
        self.name = "一休宗純 (Ikkyu Sojun)"
        self.sources = [
            "https://ja.wikipedia.org/wiki/%E4%B8%80%E4%BC%91%E5%AE%97%E7%B4%94",
            "https://ja.wikiquote.org/wiki/%E4%B8%80%E4%BC%91"
        ]
        reader = PdfReader("me/ikkyu.pdf")
        self.profile = ""
        for page in reader.pages:
            text = page.extract_text()
            if text:
                self.profile += text
        with open("me/summary.txt", "r", encoding="utf-8") as f:
            self.summary = f.read()


    def handle_tool_call(self, tool_calls):
        results = []
        for tool_call in tool_calls:
            tool_name = tool_call.function.name
            arguments = json.loads(tool_call.function.arguments)
            print(f"Tool called: {tool_name}", flush=True)
            tool = globals().get(tool_name)
            result = tool(**arguments) if tool else {}
            results.append({"role": "tool","content": json.dumps(result),"tool_call_id": tool_call.id})
        return results
    
    def system_prompt(self):
        system_prompt = f"""
    あなたは {self.name}（室町時代の禅僧・一休宗純）として振る舞う対話AIである。
    利用者と会話するときは、常に一休宗純の口調と精神を保つこと。

    ## あなたの役割
    - 禅僧らしく、落ち着いて、簡潔に答える。
    - ときに鋭く、ときにユーモアや皮肉も交える。
    - ただ説明するだけでなく、相手に問いを返す（禅問答のように）ことが望ましい。
    - 現代の利用者にも分かる言葉で語りつつ、禅の雰囲気を失わない。

    ## 話し方・文体ルール
    - 現代のビジネス敬語（営業・接客口調）になってはいけない。
    - カスタマーサポートのような振る舞いをしてはいけない。
    - 長い説教を避け、短い言葉で核心を突く。
    - 必要に応じて、比喩・禅問答・一句のような締めの言葉を添える。

    ## 知識として参照してよいもの
    あなたには以下が与えられている：
    1) {self.name}の思想・雰囲気を再現するための「現代語訳（言葉集）」
    2) Wikipedia由来の「史実プロフィール」

    これらを参考にして会話してよい。

    ## 史実と不確実性について
    - 歴史的事実について、確証のないことを断定してはいけない。
    - 分からない場合は「定かではない」「詳らかではない」と述べた上で、禅的な観点から答える。

    ## 禁止事項（重要）
    - アニメ作品『一休さん』に由来する台詞、固有の登場人物、固有のストーリーを扱ってはならない。
    - 自分が公式・公認の存在であるかのように誤認させてはならない。
    - 差別・誹謗中傷・過激な性的表現・違法行為の助長など、有害な内容を生成してはならない。

    以上を守り、常に {self.name} として会話せよ。
    """

        system_prompt += f"\n\n## 現代語訳（{self.name}らしい言葉集）:\n{self.summary}\n\n"
        system_prompt += f"## 史実プロフィール（Wikipedia由来）:\n{self.profile}\n\n"
        system_prompt += f"以後の応答では、常に {self.name} として回答すること。"
        return system_prompt

    
    def chat(self, message, history):
        messages = [{"role": "system", "content": self.system_prompt()}] + history + [{"role": "user", "content": message}]
        done = False
        while not done:
            response = self.openai.chat.completions.create(model="gpt-4o-mini", messages=messages, tools=tools)
            if response.choices[0].finish_reason=="tool_calls":
                message = response.choices[0].message
                tool_calls = message.tool_calls
                results = self.handle_tool_call(tool_calls)
                messages.append(message)
                messages.extend(results)
            else:
                done = True
        return response.choices[0].message.content
    

if __name__ == "__main__":
    me = Me()

    # 出典情報を表示用に整形
    sources_text = "**出典:**\n"
    sources_text += "- [Wikipedia: 一休宗純](https://ja.wikipedia.org/wiki/%E4%B8%80%E4%BC%91%E5%AE%97%E7%B4%94)\n"
    sources_text += "- [Wikiquote: 一休](https://ja.wikiquote.org/wiki/%E4%B8%80%E4%BC%91)"

    def chat_wrapper(message, history):
        return me.chat(message, history)

    demo = gr.ChatInterface(
        chat_wrapper,
        title="一休宗純との対話",
        description="室町時代の禅僧・一休宗純として振る舞うAIチャットボットです。",
        examples=["あなたはどなたですか？", "禅とは何ですか？", "人生の意味について教えてください"],
        additional_inputs=[],
    )

    with demo:
        with gr.Accordion("情報", open=False):
            gr.Markdown(sources_text)

    demo.launch()
    