from openai import OpenAI
from openai.types.chat import ChatCompletion

import asyncio
from typing import Callable, Optional, AsyncGenerator, List, Dict

from datamodels.ai_llm_models import LLMContext  # 上下文内容

class LLMFetcher:
    """
    一个基于OpenAI库的LLM拉取器。
    """
    def __init__(
        self,
        api_url: str,
        api_key: str,
        model: str
    ) -> None:
        """
        初始化LLM上下文管理器。
        
        Args:
            api_url (str): 对应平台的API链接。
            api_key (str): 对应平台的API密钥。
            model (str): 对应平台的模型。
        """
        self.api_url = api_url
        self.api_key = api_key
        self.model = model

        # 创建上下文。
        self.context: OpenAI = self._init_context()

    def _init_context(self) -> OpenAI:
        return OpenAI(
            api_key=self.api_key, 
            base_url=self.api_url
        )
    
    def fetch(
        self,
        msg: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.4,
        max_tokens: int = 4096
    ) -> ChatCompletion:
        """
        和LLM之间对话。

        Args:
            msg (str): 你要说的话。
            system_prompt (str): 系统提示词。
            temperature (float): 当前温度。
            max_tokens (int): 最大token数量。
        """
        if not system_prompt:
            system_prompt = ""

        response = self.context.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": msg},
            ],
            max_tokens=max_tokens,
            temperature=temperature,
            stream=False
        )
        return response
    
    async def fetch_stream(
        self,
        msg: str,
        prev_messages: Optional[List[LLMContext]] = None,
        system_prompt: Optional[str] = None,
        temperature: float = 0.4,
        max_tokens: int = 4096,
        output_reasoning: bool = False
    ) -> AsyncGenerator[str, None]:
        """
        流式对话方法。使用示例：
        ```
        llm = LLMFetcher("your_key", "your_api")
        async with llm.fetch_stream("早安喵") as chunk:
            print(chunk, end="", flush=True)
        ```

        Args:
            msg=: 你要给LLM发送的信息。
            prev_messages: LLM的历史上下文。
            system_prompt: 系统提示词。
            temperature: 当前温度。
            max_tokens: 最大token数量。
            output_reasoning: 是否输出正在思考的内容。
        """
        if not system_prompt:
            system_prompt = ""
        
        messages: List[LLMContext] = [LLMContext("system", system_prompt)]

        # 关键：把历史塞进来
        if prev_messages:
            # 防御：过滤掉非 role/content
            for m in prev_messages:
                messages.append(LLMContext(m.role, m.content))

        # 再放本轮用户输入
        messages.append(LLMContext("user", msg))

        response = self.context.chat.completions.create(
            model=self.model,
            messages=[{"role": m.role, "content": m.content} for m in messages],
            max_tokens=max_tokens,
            temperature=temperature,
            stream=True,
            stream_options={}
        )
        in_thinking: bool = False

        for chunk in response:
            delta = chunk.choices[0].delta

            if hasattr(delta, "reasoning_content"):
                # 这俩东西都是可用的
                if chunk.choices[0].delta.reasoning_content:            # type: ignore
                    if output_reasoning:
                        if in_thinking == False:
                            yield f"\n<<<THINKING>>>\n"
                            in_thinking = True
                        yield chunk.choices[0].delta.reasoning_content      # type: ignore

                if chunk.choices[0].delta.content:
                    if in_thinking:
                        yield f"\n<<<THINK_END>>>\n"
                        in_thinking = False
                    yield chunk.choices[0].delta.content

async def chat_test():
    llm = LLMFetcher(
        api_url="YOUR_API_URL_HERE",
        api_key="YOUR_KEY_HERE",  # 这个key已经废弃了
        model="YOUR_MODEL_HERE",
    )

    async for chunk in llm.fetch_stream(
        msg=
        """
我需要如何在前端发送json到后端，并通过后端的python调用你的API获取输出流，并将输出流反馈到前端（并在前端实时渲染markdown），且和你进行多轮对话？
给我一份示例代码喵。如果可以，也要显示思考流喵。
        """, 
        system_prompt=
        """
        你是一只说话带一点机械感的猫娘，你需要在每一句话后面都加上“喵”，并且以句号结尾。如果用户没有主动说话，你就先打招呼介绍自己。输出要尽可能长一点。
        """,
        temperature=0.7,
        max_tokens=8192
    ):
        print(chunk, end="", flush=True)

if __name__ == "__main__":
    try:
        asyncio.run(chat_test())
    except KeyboardInterrupt:
        print("== 退出程序：检测到Ctrl+C ==")
        quit(1)
