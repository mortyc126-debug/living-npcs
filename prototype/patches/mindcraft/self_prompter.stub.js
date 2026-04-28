// LIVING_NPCS stub: self-prompter полностью отключён.
//
// Оригинальный self_prompter каждые ~2с шлёт agent.handleMessage('system',
// "You are self-prompting with the goal: ...; Your next response MUST contain
// a command with this syntax: !commandName"). Это превращает любого NPC в
// goal-driven assistant, что прямо противоречит миссии Living NPCs
// (см. README §"Принципы проекта": "Жители мира, не симуляция людей").
//
// Стаб сохраняет всё API, которое использует src/agent/agent.js:
//   start, startLoop, update, stop, stopLoop, pause,
//   handleLoad, setPromptPaused, shouldInterrupt, handleUserPromptedCmd,
//   isActive, isStopped, isPaused.
// Все методы либо no-op, либо возвращают «всегда STOPPED». Сохранённые
// goal-цели в bots/<name>/memory.json игнорируются на загрузке.

const STOPPED = 0;

export class SelfPrompter {
    constructor(agent) {
        this.agent = agent;
        this.state = STOPPED;
        this.loop_active = false;
        this.interrupt = false;
        this.prompt = '';
        this.idle_time = 0;
        this.cooldown = 2000;
    }

    start(_prompt) {
        return 'Self-prompting disabled in living-npcs build.';
    }

    isActive() { return false; }
    isStopped() { return true; }
    isPaused() { return false; }

    async handleLoad(_prompt, _state) {
        // намеренно игнорируем сохранённые цели; начинаем каждую сессию с нуля.
        this.state = STOPPED;
        this.prompt = '';
    }

    setPromptPaused(_prompt) { /* no-op */ }

    async startLoop() { /* no-op — главная нейтрализация */ }

    update(_delta) { this.idle_time = 0; }

    async stopLoop() { this.interrupt = false; }

    async stop(_stop_action = true) { this.state = STOPPED; }

    async pause() { /* no-op */ }

    shouldInterrupt(_is_self_prompt) { return false; }

    handleUserPromptedCmd(_is_self_prompt, _is_action) { /* no-op */ }
}
