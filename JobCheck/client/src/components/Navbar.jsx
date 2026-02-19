import { Link, useNavigate } from "react-router-dom";
import { Briefcase, LogIn, UserPlus, Menu, X, LayoutDashboard, User, LogOut } from "lucide-react";
import { useState, useEffect } from "react";

const Navbar = () => {
    const [isOpen, setIsOpen] = useState(false);
    const navigate = useNavigate();
    const token = localStorage.getItem("token");

    const handleLogout = () => {
        localStorage.removeItem("token");
        navigate("/");
        setIsOpen(false);
    };

    return (
        <nav className="sticky top-0 z-50 bg-black/80 backdrop-blur-md border-b border-white/10 px-6 py-4">
            <div className="max-w-7xl mx-auto flex justify-between items-center">
                <Link to="/" className="flex items-center gap-2 group">
                    <div className="bg-gold p-1.5 rounded-lg group-hover:scale-110 transition-transform">
                        <Briefcase className="text-dark w-6 h-6" />
                    </div>
                    <span className="text-2xl font-serif font-bold tracking-tight">
                        Job<span className="text-gold">Check</span>
                    </span>
                </Link>

                {/* Desktop Menu */}
                <div className="hidden md:flex items-center gap-8">
                    <Link to="/" className="hover:text-gold transition-colors font-medium">Home</Link>

                    {token ? (
                        <>
                            <Link to="/jobs" className="hover:text-gold transition-colors font-medium">Find Jobs</Link>
                            <Link to="/feedback" className="hover:text-gold transition-colors font-medium">Feedback</Link>
                            <Link to="/dashboard" className="flex items-center gap-2 hover:text-gold transition-colors font-medium">
                                <LayoutDashboard size={18} /> Dashboard
                            </Link>
                            {localStorage.getItem("is_admin") === "true" && (
                                <Link to="/admin-dashboard" className="flex items-center gap-2 text-gold hover:text-white transition-colors font-bold uppercase tracking-tighter text-xs bg-gold/10 px-3 py-1.5 rounded-lg border border-gold/20">
                                    Admin Control
                                </Link>
                            )}
                            <Link to="/profile" className="flex items-center gap-2 hover:text-gold transition-colors font-medium">
                                <User size={18} /> Profile
                            </Link>
                            <div className="h-6 w-px bg-white/20"></div>
                            <button
                                onClick={handleLogout}
                                className="flex items-center gap-2 text-gray-400 hover:text-white transition-colors font-medium"
                            >
                                <LogOut size={18} /> Logout
                            </button>
                        </>
                    ) : (
                        <>
                            <div className="h-6 w-px bg-white/20"></div>
                            <Link to="/login" className="flex items-center gap-2 hover:text-gold transition-colors font-medium">
                                <LogIn size={18} /> Login
                            </Link>
                            <Link to="/register" className="btn-gold flex items-center gap-2 !py-2">
                                <UserPlus size={18} /> Join Now
                            </Link>
                        </>
                    )}
                </div>

                {/* Mobile Toggle */}
                <button className="md:hidden text-white" onClick={() => setIsOpen(!isOpen)}>
                    {isOpen ? <X size={28} /> : <Menu size={28} />}
                </button>
            </div>

            {/* Mobile Menu */}
            {isOpen && (
                <div className="md:hidden absolute top-full left-0 w-full bg-dark-surface border-b border-white/10 p-6 flex flex-col gap-4 animate-in slide-in-from-top duration-300">
                    <Link to="/" className="text-lg py-2 border-b border-white/5" onClick={() => setIsOpen(false)}>Home</Link>

                    {token ? (
                        <>
                            <Link to="/jobs" className="text-lg py-2 border-b border-white/5" onClick={() => setIsOpen(false)}>Find Jobs</Link>
                            <Link to="/feedback" className="text-lg py-2 border-b border-white/5" onClick={() => setIsOpen(false)}>Feedback</Link>
                            <Link to="/dashboard" className="text-lg py-2 border-b border-white/5" onClick={() => setIsOpen(false)}>Dashboard</Link>
                            {localStorage.getItem("is_admin") === "true" && (
                                <Link to="/admin-dashboard" className="text-lg py-2 border-b border-gold/20 text-gold font-bold" onClick={() => setIsOpen(false)}>Admin Control</Link>
                            )}
                            <Link to="/profile" className="text-lg py-2 border-b border-white/5" onClick={() => setIsOpen(false)}>Profile</Link>
                            <button
                                onClick={handleLogout}
                                className="text-lg py-2 text-left text-red-400 font-medium"
                            >
                                Logout
                            </button>
                        </>
                    ) : (
                        <>
                            <Link to="/login" className="text-lg py-2 border-b border-white/5" onClick={() => setIsOpen(false)}>Login</Link>
                            <Link to="/register" className="btn-gold text-center py-3" onClick={() => setIsOpen(false)}>Join Now</Link>
                        </>
                    )}
                </div>
            )}
        </nav>
    );
};

export default Navbar;
