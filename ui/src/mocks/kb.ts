const MOCK_ANSWER =
  '## Python 装饰器原理\n\n' +
  '装饰器本质上是一个**高阶函数**，它接收一个函数作为参数，返回一个新函数。\n\n' +
  '### 基本语法\n\n' +
  '```python\ndef my_decorator(func):\n    def wrapper(*args, **kwargs):\n        print("Before")\n        result = func(*args, **kwargs)\n        print("After")\n        return result\n    return wrapper\n\n@my_decorator\ndef say_hello():\n    print("Hello!")\n```\n\n' +
  '### 执行流程\n\n' +
  '1. `@my_decorator` 等价于 `say_hello = my_decorator(say_hello)`\n' +
  '2. 调用 `say_hello()` 实际执行的是 `wrapper()`\n' +
  '3. `wrapper` 内部调用原始 `func()` 并可在前后添加逻辑\n\n' +
  '### 带参数的装饰器\n\n' +
  '需要再嵌套一层函数：\n\n' +
  '```python\ndef repeat(n):\n    def decorator(func):\n        def wrapper(*args, **kwargs):\n            for _ in range(n):\n                func(*args, **kwargs)\n        return wrapper\n    return decorator\n```\n\n' +
  '`functools.wraps` 用于保留原函数的 `__name__` 和 `__doc__` 属性。'

/**
 * 模拟 SSE 流式输出，逐字回调
 * 通过 signal 检测取消
 */
export function mockKBStream(
  onChunk: (text: string) => void,
  onDone: () => void,
  onError: (err: Error) => void,
  signal?: AbortSignal
): void {
  let index = 0
  const chars = [...MOCK_ANSWER]

  function tick() {
    if (signal?.aborted) {
      onError(new Error('aborted'))
      return
    }
    if (index >= chars.length) {
      onDone()
      return
    }
    onChunk(chars[index])
    index++
    setTimeout(tick, 50)
  }

  // 模拟网络延迟后开始输出
  setTimeout(() => {
    if (signal?.aborted) {
      onError(new Error('aborted'))
      return
    }
    tick()
  }, 300)
}

/**
 * 同步查询 mock
 */
export function mockKBQuery() {
  return {
    answer: MOCK_ANSWER,
    sources: [
      { content: 'Python 官方文档 - 装饰器', metadata: { source: 'docs.python.org' } },
      { content: 'Real Python - Primer on Decorators', metadata: { source: 'realpython.com' } },
    ],
  }
}
