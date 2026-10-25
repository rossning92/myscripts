export PATH="$HOME/myscripts/bin:$PATH"

# If not running interactively, don't do anything
[[ $- != *i* ]] && return

alias c='xclip -selection clipboard'
alias grep='grep --color=auto'
alias i='sudo pacman -S --noconfirm'
alias ls='ls --color=auto'
alias v=nvim

if [[ -n "$TERMUX_VERSION" ]]; then
	[[ "$(tty)" == "/dev/pts/0" ]] && $HOME/myscripts/myscripts --startup
fi
