import wx

from twitch_chat_helper.chat_frame import ChatFrame


def main() -> None:
    application = wx.App(redirect=False)
    application.SetAppName("TwitchChatHelper")
    main_frame = ChatFrame()
    main_frame.Show()
    application.MainLoop()


if __name__ == "__main__":
    main()
