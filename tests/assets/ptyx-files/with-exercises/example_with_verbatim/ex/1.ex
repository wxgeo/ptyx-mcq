...............
def func(M):
    """comment."""
    M = numpy.copy(M)
    m, n = M.shape  # m: nombre de lignes, n: nombre de colonnes
    i0, j0 = 0, 0  # i: numéro de ligne, j: numéro de colonne
    while i0 < m - 1 and j0 < n:
        for i in range(i0, m):
            if M[i][j0] != 0:
                M[[i, i0]] = M[[i0, i]]
                assert M[i0][j0] != 0  # pivot
                for i in range(i0 + 1, m):
                    M[i] += -M[i][j0]/M[i0][j0]*M[i0]
                    assert M[i][j0] == 0
                i0 += 1
                break
        j0 += 1
    return M
        
let a, b, c, d, e, f, g, h, i

A = Matrix([[a, b, c], [d, e, f], [g, h, i]])

M = numpy.array([[a, b, c, 1, 0, 0], [d, e, f, 0, 1, 0], [g, h, i, 0, 1, 0]])

M=Matrix(M)

N = Matrix(func(M))

rep = ["answer 1", "answer 2", "answer 3"]
ok = ["answer 1", "answer 3"]
.......................

Let $B=#{N[:,3:]}$.

#ANSWERS_LIST{rep}{ok}
