import { createContext, useContext, useEffect, useState } from 'react'
import {
  onAuthStateChanged,
  createUserWithEmailAndPassword,
  signInWithEmailAndPassword,
  signInWithPopup,
  signOut as firebaseSignOut,
  updateProfile,
} from 'firebase/auth'
import { doc, getDoc, setDoc, serverTimestamp } from 'firebase/firestore'
import { auth, db, googleProvider } from '../lib/firebase'

const AuthContext = createContext({})

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [profile, setProfile] = useState(null)
  const [loading, setLoading] = useState(true)

  async function fetchProfile(uid) {
    const snap = await getDoc(doc(db, 'users', uid))
    if (snap.exists()) {
      setProfile(snap.data())
    }
  }

  useEffect(() => {
    const unsubscribe = onAuthStateChanged(auth, async (firebaseUser) => {
      setUser(firebaseUser)
      if (firebaseUser) {
        await fetchProfile(firebaseUser.uid)
      } else {
        setProfile(null)
      }
      setLoading(false)
    })
    return () => unsubscribe()
  }, [])

  async function signUp(email, password, displayName) {
    try {
      const { user: newUser } = await createUserWithEmailAndPassword(auth, email, password)
      await updateProfile(newUser, { displayName })

      await setDoc(doc(db, 'users', newUser.uid), {
        email,
        display_name: displayName,
        created_at: serverTimestamp(),
        bankroll: {
          current: 500.00,
          starting: 500.00,
          last_updated: serverTimestamp(),
        },
      })

      await fetchProfile(newUser.uid)
      return { data: newUser, error: null }
    } catch (err) {
      return { data: null, error: { message: err.message } }
    }
  }

  async function signIn(email, password) {
    try {
      const { user: loggedIn } = await signInWithEmailAndPassword(auth, email, password)
      return { data: loggedIn, error: null }
    } catch (err) {
      return { data: null, error: { message: err.message } }
    }
  }

  async function signInWithGoogle() {
    try {
      const { user: googleUser } = await signInWithPopup(auth, googleProvider)

      const userRef = doc(db, 'users', googleUser.uid)
      const snap = await getDoc(userRef)
      if (!snap.exists()) {
        await setDoc(userRef, {
          email: googleUser.email,
          display_name: googleUser.displayName || googleUser.email.split('@')[0],
          created_at: serverTimestamp(),
          bankroll: {
            current: 500.00,
            starting: 500.00,
            last_updated: serverTimestamp(),
          },
        })
      }

      await fetchProfile(googleUser.uid)
      return { data: googleUser, error: null }
    } catch (err) {
      return { data: null, error: { message: err.message } }
    }
  }

  async function signOut() {
    await firebaseSignOut(auth)
    setUser(null)
    setProfile(null)
  }

  return (
    <AuthContext.Provider value={{ user, profile, loading, signUp, signIn, signInWithGoogle, signOut, fetchProfile }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  return useContext(AuthContext)
}
