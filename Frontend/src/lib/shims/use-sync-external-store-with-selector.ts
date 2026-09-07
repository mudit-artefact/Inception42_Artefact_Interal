import * as React from "react";

export function useSyncExternalStoreWithSelector<Snapshot, Selection>(
  subscribe: (onStoreChange: () => void) => () => void,
  getSnapshot: () => Snapshot,
  getServerSnapshot: undefined | null | (() => Snapshot),
  selector: (snapshot: Snapshot) => Selection,
  isEqual?: (a: Selection, b: Selection) => boolean
): Selection {
  const instRef = React.useRef<{
    hasValue: boolean;
    value: Selection;
    getSnapshot: () => Snapshot;
    selector: (snapshot: Snapshot) => Selection;
    isEqual?: (a: Selection, b: Selection) => boolean;
  } | null>(null);

  if (instRef.current === null) {
    instRef.current = {
      hasValue: false,
      value: undefined as unknown as Selection,
      getSnapshot,
      selector,
      isEqual,
    };
  } else {
    instRef.current.getSnapshot = getSnapshot;
    instRef.current.selector = selector;
    instRef.current.isEqual = isEqual;
  }

  const getSelection = React.useCallback(() => {
    const nextSnapshot = getSnapshot();
    const inst = instRef.current;
    if (inst) {
      if (inst.hasValue) {
        const prevValue = inst.value;
        const nextValue = selector(nextSnapshot);
        if (isEqual ? isEqual(prevValue, nextValue) : Object.is(prevValue, nextValue)) {
          return prevValue;
        }
        inst.value = nextValue;
        return nextValue;
      }
      const nextValue = selector(nextSnapshot);
      inst.hasValue = true;
      inst.value = nextValue;
      return nextValue;
    }
    return selector(nextSnapshot);
  }, [getSnapshot, selector, isEqual]);

  const getServerSelection = React.useMemo(() => {
    if (!getServerSnapshot) return undefined;
    return () => selector(getServerSnapshot());
  }, [getServerSnapshot, selector]);

  return React.useSyncExternalStore(subscribe, getSelection, getServerSelection);
}

export default { useSyncExternalStoreWithSelector };
