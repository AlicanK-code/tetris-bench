def score(board, placement):
    lines = placement["lines_cleared"]
    total = lines * 100

    min_top = 20
    for col in range(10):
        for row in range(20):
            if board[row][col]:
                if row < min_top:
                    min_top = row
                break

    total += min_top * 5

    holes = 0
    for col in range(10):
        found_filled = False
        for row in range(20):
            if board[row][col]:
                found_filled = True
            else:
                if found_filled:
                    holes += 1

    total -= holes * 2

    top_rows = []
    for col in range(10):
        top_row = 20
        for row in range(20):
            if board[row][col]:
                top_row = row
                break
        if top_row != 20:
            top_rows.append(top_row)
    
    surface_diff = max(top_rows) - min(top_rows) if top_rows else 0
    total -= surface_diff * 10

    total += placement["column"] / 1000.0

    return total
