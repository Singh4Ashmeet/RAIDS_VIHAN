import { motion, AnimatePresence } from 'framer-motion'

export default function Modal({
  open, onClose, title, children, footer
}) {
  return (
    <AnimatePresence>
      {open && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="fixed inset-0 bg-black/60 backdrop-blur-sm
            z-50 flex items-center justify-center p-4"
          onClick={onClose}
        >
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.95 }}
            transition={{ duration: 0.15 }}
            role="dialog"
            aria-modal="true"
            aria-label={title}
            className="w-full max-w-lg rounded-xl border
              border-white/10 bg-[#151c2e] shadow-2xl shadow-black/50"
            onClick={e => e.stopPropagation()}
          >
            <div className="border-b border-white/10 p-6">
              <h2 className="text-lg font-semibold text-slate-100">
                {title}
              </h2>
            </div>
            <div className="p-6">{children}</div>
            {footer && (
              <div className="flex border-t border-white/10 p-6
                justify-end gap-3">
                {footer}
              </div>
            )}
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}
