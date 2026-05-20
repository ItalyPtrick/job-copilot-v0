export function getToastViewportClass(isMockMode: boolean) {
  return `fixed right-4 ${isMockMode ? 'top-12' : 'top-4'} z-[60] flex flex-col gap-3`
}
