export default function AuthLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-gray-50 via-cyan-50/30 to-gray-50 px-4">
      {children}
    </div>
  );
}
