import { motion } from 'framer-motion'
import { LogOut, Menu, Moon, Settings, Sun, Ticket, User as UserIcon } from 'lucide-react'
import { useState } from 'react'
import { Link, NavLink, useNavigate } from 'react-router'

import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { GradientButton } from '@/components/ui/GradientButton'
import { Separator } from '@/components/ui/separator'
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetTrigger } from '@/components/ui/sheet'
import { useAuth } from '@/hooks/useAuth'
import { useTheme } from '@/hooks/useTheme'
import { cn } from '@/lib/utils'

import { Logo } from './Logo'
import { getNavItems, type NavItem } from './navConfig'

function initials(name: string): string {
  return (
    name
      .split(/\s+/)
      .filter(Boolean)
      .slice(0, 2)
      .map((p) => p[0]?.toUpperCase() ?? '')
      .join('') || '?'
  )
}

function DesktopNavLink({ item }: { item: NavItem }) {
  return (
    <NavLink
      to={item.to}
      end={!item.matchNested}
      className={({ isActive }) =>
        cn(
          'relative rounded-full px-3 py-2 text-sm font-medium text-muted-foreground transition-colors hover:text-foreground',
          isActive && 'text-foreground',
        )
      }
    >
      {({ isActive }) => (
        <>
          {isActive && (
            <motion.span
              layoutId="nav-active-pill"
              className="absolute inset-0 -z-10 rounded-full bg-primary/10"
              transition={{ type: 'spring', stiffness: 400, damping: 30 }}
            />
          )}
          {item.label}
        </>
      )}
    </NavLink>
  )
}

function ThemeToggle() {
  const { resolvedTheme, toggleTheme } = useTheme()
  return (
    <Button
      variant="ghost"
      size="icon"
      onClick={toggleTheme}
      aria-label={resolvedTheme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme'}
    >
      {resolvedTheme === 'dark' ? <Sun /> : <Moon />}
    </Button>
  )
}

export function Navbar() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const [mobileOpen, setMobileOpen] = useState(false)
  const items = getNavItems(user?.role ?? null)

  const handleLogout = async () => {
    setMobileOpen(false)
    await logout()
    navigate('/login', { replace: true })
  }

  return (
    <header className="sticky top-0 z-40 w-full border-b border-border/60 bg-background/75 backdrop-blur-xl">
      <div className="container mx-auto flex h-16 max-w-7xl items-center gap-4 px-4 sm:px-6 lg:px-8">
        <Link to="/" className="shrink-0" aria-label="TurfSlot home">
          <Logo />
        </Link>

        <nav aria-label="Main" className="isolate ml-4 hidden items-center gap-1 lg:flex">
          {items.map((item) => (
            <DesktopNavLink key={item.to} item={item} />
          ))}
        </nav>

        <div className="ml-auto flex items-center gap-2">
          <ThemeToggle />

          {user ? (
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="ghost" className="h-10 gap-2 rounded-full px-1.5 sm:pr-3" aria-label="Account menu">
                  <Avatar className="size-8">
                    <AvatarFallback className="bg-primary/15 text-xs font-semibold text-primary">
                      {initials(user.full_name)}
                    </AvatarFallback>
                  </Avatar>
                  <span className="hidden max-w-32 truncate text-sm font-medium sm:inline">{user.full_name}</span>
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-60">
                <DropdownMenuLabel className="space-y-1">
                  <p className="truncate text-sm font-semibold">{user.full_name}</p>
                  <p className="truncate text-xs font-normal text-muted-foreground">{user.email}</p>
                  <Badge variant="secondary" className="capitalize">
                    {user.role}
                  </Badge>
                </DropdownMenuLabel>
                <DropdownMenuSeparator />
                <DropdownMenuItem asChild>
                  <Link to="/profile">
                    <UserIcon /> Profile
                  </Link>
                </DropdownMenuItem>
                {user.role !== 'admin' && (
                  <DropdownMenuItem asChild>
                    <Link to="/my-bookings">
                      <Ticket /> My Bookings
                    </Link>
                  </DropdownMenuItem>
                )}
                <DropdownMenuItem asChild>
                  <Link to="/settings">
                    <Settings /> Settings
                  </Link>
                </DropdownMenuItem>
                <DropdownMenuSeparator />
                <DropdownMenuItem variant="destructive" onSelect={() => void handleLogout()}>
                  <LogOut /> Log out
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          ) : (
            <div className="hidden items-center gap-2 sm:flex">
              <Button variant="ghost" asChild>
                <Link to="/login">Log in</Link>
              </Button>
              <GradientButton size="default" onClick={() => navigate('/register')}>
                Get started
              </GradientButton>
            </div>
          )}

          <Sheet open={mobileOpen} onOpenChange={setMobileOpen}>
            <SheetTrigger asChild>
              <Button variant="ghost" size="icon" className="lg:hidden" aria-label="Open menu">
                <Menu />
              </Button>
            </SheetTrigger>
            <SheetContent side="right" className="w-72">
              <SheetHeader>
                <SheetTitle>
                  <Logo />
                </SheetTitle>
              </SheetHeader>
              <nav aria-label="Mobile" className="flex flex-col gap-1 px-4">
                {items.map((item) => (
                  <NavLink
                    key={item.to}
                    to={item.to}
                    end={!item.matchNested}
                    onClick={() => setMobileOpen(false)}
                    className={({ isActive }) =>
                      cn(
                        'flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors hover:bg-accent',
                        isActive ? 'bg-primary/10 text-primary' : 'text-muted-foreground',
                      )
                    }
                  >
                    <item.icon className="size-4" aria-hidden="true" />
                    {item.label}
                  </NavLink>
                ))}
                <Separator className="my-3" />
                {user ? (
                  <>
                    <Link
                      to="/profile"
                      onClick={() => setMobileOpen(false)}
                      className="flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium text-muted-foreground hover:bg-accent"
                    >
                      <UserIcon className="size-4" aria-hidden="true" /> Profile
                    </Link>
                    <Link
                      to="/settings"
                      onClick={() => setMobileOpen(false)}
                      className="flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium text-muted-foreground hover:bg-accent"
                    >
                      <Settings className="size-4" aria-hidden="true" /> Settings
                    </Link>
                    <Button
                      variant="ghost"
                      className="justify-start gap-3 px-3 text-destructive hover:text-destructive"
                      onClick={() => void handleLogout()}
                    >
                      <LogOut /> Log out
                    </Button>
                  </>
                ) : (
                  <div className="flex flex-col gap-2">
                    <Button variant="outline" asChild>
                      <Link to="/login" onClick={() => setMobileOpen(false)}>
                        Log in
                      </Link>
                    </Button>
                    <GradientButton
                      size="default"
                      onClick={() => {
                        setMobileOpen(false)
                        navigate('/register')
                      }}
                    >
                      Get started
                    </GradientButton>
                  </div>
                )}
              </nav>
            </SheetContent>
          </Sheet>
        </div>
      </div>
    </header>
  )
}
