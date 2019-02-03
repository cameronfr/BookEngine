var API_URL = "https://asia-northeast1-traininggpu.cloudfunctions.net/GutenBert"
var API_HELPER_URL = "https://asia-northeast1-traininggpu.cloudfunctions.net/GutenBertHelper"

var fetchFromServer = (url, body) => {
	return fetch(url, {
		method: "POST",
		mode: "cors",
		headers: {"Content-Type": "application/json"},
		body: JSON.stringify(body)
	}).then(res => res.json())
}

class App extends React.Component {

	style = {
		width: "700px",
		maxWidth: "700px",
		fontSize: "16px",
		fontFamily: "Arial",
		lineHeight: 1.3
	}

	constructor(props) {
		super(props)
		this.state = {
			units: [],
			isWaitingForResults: false,
			searchText: "",
			errorMessage: "",
		}
	}

	search() {
		this.setState({isWaitingForResults: true})
		fetchFromServer(API_URL, {"sentence": this.state.searchText}).then(res => {
			this.setState({units: res.textUnits, error: "", isWaitingForResults: false})
		}).catch(err => {
			var errorMessage = (err.response && err.response.data.msg) || "Error calling API"
			this.setState({isWaitingForResults: false, errorMessage})
		})
	}

	render() {
		var updateSearchText = e => this.setState({searchText: e.target.value})
		var submitSearch = e => {e.preventDefault(); this.search()}

		return (
		 <div style={{height: "100%", display: "flex", justifyContent: "center"}}>
			 <div style={this.style}>
				 {this.state.errorMessage && this.state.errorMessage}
				 <h1>Book Engine</h1>
				 <SearchBar
					 onSubmit={submitSearch}
					 onChange={updateSearchText}
					 disabled={false}
					 placeholder={this.state.searchText}
					 value={this.state.searchText}
					/>
				{this.state.units.map(unit => <ResultItem key={unit.vectorNum} unit={unit} />)}
			 </div>
		 </div>
		)
	}

}

class SearchBar extends React.Component{

	inputStyle = {
		width: "100%",
		boxShadow: "0px 1px 4px #ccc",
		border: "none",
		outline: "none",
		// height: "30px",
		borderRadius: "4px",
		padding: "10px",
		fontFamily: "inherit",
		fontSize: "inherit",
	}

  constructor(props){
    super(props);
  }

  render() {
    return (
      <div style={{width: "100%", boxSizing: "border-box"}}>
        <form onSubmit={this.props.onSubmit}>
	        <div uk-grid="true">
	          <input style={this.inputStyle}
							placeholder={this.props.placeholder}
							onChange={this.props.onChange}
							disabled={this.props.disabled}
							value={this.props.value}
						/>
	        </div>
        </form>
      </div>
    )
  }
}

class ResultItem extends React.Component {

	style = {
		// boxShadow: "0px 0px 3px #ccc",
		padding: "10px",
		paddingBottom: "20px",
		paddingTop: "20px",
		cursor: "pointer",
	}

	textAreaStyle = {
		padding: "5px",
		paddingRight: "15px", //scroll bar space
	}

	infoStringStyle = {
		marginTop: "10px",
		textAlign: "right",
		fontSize: "16px",
		width: "60%",
		padding: "5px",
		borderRadius: "5px",
		border: "1px solid #000",
	}

	constructor(props) {
		super(props)
		this.state = {
			expanded: false,
			hovering: false,
			isLoading: false,
			units: [this.props.unit],
		}
		this.textAreaRef = React.createRef()
	}

	formatText(text) {
		text = text.replace("--", "—") //em dash
		var parts = text.split(/(_.+?_|=.+?=)/g)
		for(var i=1; i<parts.length; i+=2) {
			if (parts[i][0] == "_") {
				var part = parts[i].slice(1, parts[1].length-1)
				parts[i] = <b key={i}>{part}</b>
			}
			else if (parts[i][0] == "=") {
				var part = parts[i].slice(1, parts[1].length-1)
				parts[i] = <i key={i}>{part}</i>
			}
		}
		return parts
	}

	range(start, end) {
		var range = []
		for (var i=start; i<end; i++) {
			range.push(i)
		}
		return range
	}

	fetchMoreText() {
		var numToAdd = 10
		var bookNum = this.props.unit.bookNum
		if (this.state.isLoading) {
			return
		}
		this.setState({isLoading: true})
		var start = this.state.units[this.state.units.length-1].inBookLocation + 1
		var inBookLocations = this.range(start, start+numToAdd)
		var bottomPromise = fetchFromServer(API_HELPER_URL, {bookNum, inBookLocations})
		var end = this.state.units[0].inBookLocation
		var inBookLocations= this.range(end-numToAdd, end)
		var topPromise = fetchFromServer(API_HELPER_URL, {bookNum, inBookLocations})
		//Updates bottom first, then top
		Promise.all([bottomPromise, topPromise]).then(allRes => {
			this.setState(state => ({units: [...state.units, ...allRes[0].textUnits]}), () => {
				this.setState(state => {
					var prevHeight = this.textAreaRef.current.scrollHeight
					var prevScrollTop = this.textAreaRef.current.scrollTop //chrome modifies scrollTop when content added to top
					return ({units: [...allRes[1].textUnits, ...state.units], isLoading: false, prevHeight, prevScrollTop})
				}, () => {
					var heightDiff = this.textAreaRef.current.scrollHeight - this.state.prevHeight
					this.textAreaRef.current.scrollTop = this.state.prevScrollTop + heightDiff
				})
			})
		})
	}

	render() {
		var unit = this.props.unit
		var onHover = e => this.setState({hovering: true})
		var onUnHover = e => this.setState({hovering: false})
		var onClick = e => {
			this.setState({expanded: true})
			this.fetchMoreText()
		}
		// var onClick = e => this.setState(state => ({expanded: !state.expanded}))
		var hoverStyle = this.state.hovering ? {boxShadow: "0px 0px 3px #ccc"} : {}
		var expandedStyle = this.state.expanded ? {height: "80%", overflow: "auto"} : {}
		var fields = ["Title", "Author", "Author Birth", "Author Death"]
		var [title, author, birth, death] = fields.map(k => (unit[k][0] ? unit[k][0] : "?"))
		var includeAuthorString = (birth != "?") || (death != "?")
		var authorString = "(" + birth + " - " + death + ")"
		var infoString = title + " — " + author + " " + (includeAuthorString ? authorString : "")
		var infoDiv = <div style={this.infoStringStyle}>{infoString}</div>

		//can make heuristic: table of contents (e.g. search "test12345") have a bunch of em dashes in them.
		// So say if the number of dashes exceeds ten, then break at those dashes.

		return (
			<React.Fragment>
				<div style={{...this.style, ...hoverStyle}}
					onMouseOver={onHover}
					onMouseLeave={onUnHover}
					onClick={onClick}>
					<div ref={this.textAreaRef} style={{...this.textAreaStyle, ...expandedStyle}}>
						<div>{this.formatText(this.state.units[0]["textUnit"])}</div>
						{this.state.units.slice(1).map(tu => (
							<React.Fragment key={tu["inBookLocation"]}>
								<br></br>
								<div>{this.formatText(tu["textUnit"])}</div>
							</React.Fragment>
						))}
					</div>
					<div style={{display: "flex", justifyContent: "flex-end"}}>
						{this.state.expanded && infoDiv}
					</div>
				</div>
				<div style={{width: "100%", border: "none", height: "1px", backgroundColor: "black"}}/>
			</React.Fragment>
		)
	}
}
ReactDOM.render(<App />, document.getElementById('root'));
