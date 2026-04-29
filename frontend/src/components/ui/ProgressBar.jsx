import clsx from 'clsx'

const WIDTH_CLASSES = [
  'w-0',
  'w-[5%]',
  'w-[10%]',
  'w-[15%]',
  'w-[20%]',
  'w-[25%]',
  'w-[30%]',
  'w-[35%]',
  'w-[40%]',
  'w-[45%]',
  'w-[50%]',
  'w-[55%]',
  'w-[60%]',
  'w-[65%]',
  'w-[70%]',
  'w-[75%]',
  'w-[80%]',
  'w-[85%]',
  'w-[90%]',
  'w-[95%]',
  'w-full',
]

const SIZE_CLASSES = {
  sm: 'h-1',
  md: 'h-2',
  lg: 'h-2.5',
}

function widthClass(percent) {
  const bucket = Math.min(20, Math.max(0, Math.round(percent / 5)))
  return WIDTH_CLASSES[bucket]
}

export default function ProgressBar({
  value = 0,
  max = 100,
  className = 'bg-brand-500',
  size = 'md',
  trackClassName = 'bg-slate-800',
}) {
  const percent = Math.min(100, Math.max(0, (Number(value || 0) / max) * 100))
  const height = SIZE_CLASSES[size] || SIZE_CLASSES.md
  return (
    <div className={clsx(height, 'rounded-full', trackClassName)}>
      <div
        className={clsx(height, 'rounded-full transition-[width]', widthClass(percent), className)}
      />
    </div>
  )
}
