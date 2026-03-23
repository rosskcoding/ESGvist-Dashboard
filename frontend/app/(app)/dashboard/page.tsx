"use client";

export default function DashboardPage() {
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-gray-900">Dashboard</h2>
        <p className="mt-1 text-sm text-gray-500">
          Welcome to ESGvist. Your ESG reporting starts here.
        </p>
      </div>

      <div className="rounded-xl border border-gray-200 bg-white p-8 text-center">
        <p className="text-gray-400">
          Create your first ESG report to get started.
        </p>
        <button className="mt-4 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-500">
          Create Project
        </button>
      </div>
    </div>
  );
}
