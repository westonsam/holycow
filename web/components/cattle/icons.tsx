export function CowMark({ size = 35 }: { size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 40 40"
      fill="none"
      aria-hidden="true"
    >
      <path
        d="M12 10 8 7 2 10l5 5 5-1M28 10l4-3 6 3-5 5-5-1M12 10l3-3h10l3 3-1 12-4 10h-6l-4-10-1-12Z"
        stroke="currentColor"
        strokeWidth="2.4"
        strokeLinejoin="round"
      />
      <path
        d="m14 18 3 2m9-2-3 2m-6 8h6m-5-4 2 2 2-2"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
      />
    </svg>
  );
}
