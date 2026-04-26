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
            className="bg-card rounded-2xl shadow-2xl border
              border-border w-full max-w-lg"
            onClick={e => e.stopPropagation()}
          >
            <div className="p-6 border-b border-border">
              <h2 className="text-lg font-semibold text-slate-100">
                {title}
              </h2>
            </div>
            <div className="p-6">{children}</div>
            {footer && (
              <div className="p-6 border-t border-border flex
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
