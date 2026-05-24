import { useCallback, useRef, useState } from 'react';

export type ToastKind = 'info' | 'success' | 'error';

export function useToast() {
  const [toast, setToast] = useState({ text: '', kind: 'info' as ToastKind, visible: false });
  const timer = useRef<number | null>(null);

  const showToast = useCallback((text: string, kind: ToastKind = 'info') => {
    setToast({ text, kind, visible: true });
    if (timer.current) window.clearTimeout(timer.current);
    timer.current = window.setTimeout(() => {
      setToast((t) => ({ ...t, visible: false }));
    }, 2800);
  }, []);

  const handleError = useCallback((err: unknown) => {
    const msg =
      (err as { payload?: { message?: string }; message?: string })?.payload?.message ||
      (err as Error).message ||
      '请求失败';
    showToast(msg, 'error');
    console.error(err);
  }, [showToast]);

  return { toast, showToast, handleError };
}
