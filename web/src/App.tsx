import { Navigate, Route, Routes } from "react-router-dom";
import Layout from "./components/Layout";
import { Spinner, Toaster } from "./components/ui";
import { useAuth } from "./hooks/useAuth";
import Login from "./pages/Login";
import Dashboard from "./pages/Dashboard";
import Courses from "./pages/Courses";
import CourseDetail from "./pages/CourseDetail";
import Lesson from "./pages/Lesson";
import Quiz from "./pages/Quiz";
import Labs from "./pages/Labs";
import LabWorkspace from "./pages/LabWorkspace";
import Ctf from "./pages/Ctf";
import Leaderboard from "./pages/Leaderboard";
import Monitor from "./pages/Monitor";
import Admin from "./pages/admin/Admin";

export default function App() {
  const { user, loading } = useAuth();
  if (loading) return <Spinner />;
  return (
    <>
      <Toaster />
      {!user ? (
        <Routes>
          <Route path="*" element={<Login />} />
        </Routes>
      ) : (
        <Routes>
          <Route element={<Layout />}>
            <Route index element={<Dashboard />} />
            <Route path="courses" element={<Courses />} />
            <Route path="courses/:key" element={<CourseDetail />} />
            <Route path="lessons/:id" element={<Lesson />} />
            <Route path="quizzes/:id" element={<Quiz />} />
            <Route path="labs" element={<Labs />} />
            <Route path="labs/:slug" element={<LabWorkspace />} />
            <Route path="ctf" element={<Ctf />} />
            <Route path="leaderboard" element={<Leaderboard />} />
            <Route path="monitor" element={<Monitor />} />
            <Route path="admin/*" element={<Admin />} />
            <Route path="*" element={<Navigate to="/" />} />
          </Route>
        </Routes>
      )}
    </>
  );
}
