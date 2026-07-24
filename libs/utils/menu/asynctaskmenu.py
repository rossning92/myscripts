from inspect import signature
from threading import Event, Thread
from typing import Any, Callable

from ..spinner import Spinner
from .menu import Menu


class AsyncTaskMenu(Menu):
    def __init__(self, target: Callable, prompt: str = "", **kwargs):
        super().__init__(prompt=prompt, **kwargs)

        self.__prompt = prompt
        self.__stop_event = Event()
        self.__result = None
        self.__exception = None

        kwargs = {}
        if "stop_event" in signature(target).parameters:
            kwargs["stop_event"] = self.__stop_event

        def wrapper():
            try:
                self.__result = target(**kwargs)
            except Exception as e:
                self.__exception = e

        self.__thread = Thread(
            target=wrapper,
        )
        self.__spinner = Spinner()
        self.__thread.start()

    def on_close(self):
        self.__stop_event.set()
        self.__thread.join()

    def on_idle(self):
        if not self.__thread.is_alive():
            if self.__exception is not None:
                raise self.__exception
            self.close()
        else:
            self.set_prompt(self.__prompt + " " + self.__spinner.frame)
            self.__spinner.advance()

    def get_result(self) -> Any:
        return self.__result
