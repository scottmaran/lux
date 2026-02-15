---
title: "On bad advice"
source_url: https://www.scattered-thoughts.net/writing/on-bad-advice/
published: 2021-09-22
captured: 2026-02-15T11:49:31-05:00
tags: [advice]
---

# On bad advice

*Published 2021-09-22*

*This post is part of a series, starting at [Reflections on a decade of coding](https://www.scattered-thoughts.net/writing/reflections-on-a-decade-of-coding/).*

Like many programmers, I'm largely self-taught. I've rarely worked with anyone more experienced than myself, especially early in my career where I spent a lot of time working with other 20-something-year-olds who also had only a few years of experience. So we all learned about how to program from advice we found on the internet, especially posts that were shared via sites like reddit and hacker news.

Much of my progress since then has been unlearning all those things. In hindsight, most of the writing and discussion I read online about how to program was actively harmful to my ability to successfully produce working code.

That's not to say that most programmers are bad programmers. Just that it's not automatically the case that good programmers will produce good advice, or that good advice will be more widely shared than bad advice.

## Context matters.

The paradox of choice is a widely told folktale about a single experiment in which putting more kinds of jam on a supermarket display resulted in less purchases. The given explanation is that choice is stressful and so some people, facing too many possible jams, will just bounce out entirely and go home without jam. This experiment is constantly cited in news and media, usually with descriptions like "scientists have discovered that choice is bad for you".

But if you go to a large supermarket you will see approximately 12 million varieties of jam. Have they not heard of the jam experiment? Jim Manzi relates in [Uncontrolled](https://www.goodreads.com/book/show/13237711-uncontrolled):

> First, note that all of the inference is built on the purchase of a grand total of thirty-five jars of jam. Second, note that if the results of the jam experiment were valid and applicable with the kind of generality required to be relevant as the basis for economic or social policy, it would imply that many stores could eliminate 75 percent of their products and cause sales to increase by 900 percent. That would be a fairly astounding result and indicates that there may be a problem with the measurement.
>
> [...] the researchers in the original experiment themselves were careful about their explicit claims of generalizability, and significant effort has been devoted to the exact question of finding conditions under which choice overload occurs consistently, but popularizers telescoped the conclusions derived from one coupon-plus-display promotion in one store on two Saturdays, up through assertions about the impact of product selection for jam for this store, to the impact of product selection for jam for all grocery stores in America, to claims about the impact of product selection for all retail products of any kind in every store, ultimately to fairly grandiose claims about the benefits of choice to society. But as we saw, testing this kind of claim in fifty experiments in different situations throws a lot of cold water on the assertion.
>
> As a practical business example, even a simplification of the causal mechanism that comprises a useful forward prediction rule is unlikely to be much like 'Renaming QwikMart stores to FastMart will cause sales to rise,' but will instead tend to be more like 'Renaming QwikMart stores to FastMart in high-income neighborhoods on high-traffic roads will cause sales to rise, as long as the store is closed for painting for no more than two days.' It is extremely unlikely that we would know all of the possible hidden conditionals before beginning testing, and be able to design and execute one test that discovers such a condition-laden rule.
>
> Further, these causal relationships themselves can frequently change. For example, we discover that a specific sales promotion drives a net gain in profit versus no promotion in a test, but next year when a huge number of changes occurs - our competitors have innovated with new promotions, the overall economy has deteriorated, consumer traffic has shifted somewhat from malls to strip centers, and so on - this rule no longer holds true. To extend the prior metaphor, we are finding our way through our dark room by bumping our shins into furniture, while unobserved gremlins keep moving the furniture around on us. For these reasons, it is not enough to run an experiment, find a causal relationship, and assume that it is widely applicable. We must run tests and then measure the actual predictiveness of the rules developed from these tests in actual implementation.

This is what I think about whenever I see a blog post with a pithy wisdom drawn from a single experience in a single domain. 'Programming' covers an enormous range of activities with different problem domains, team sizes, management structures, project lifespans, deployment sizes, deployment frequencies, hardware, performance requirements, consequences for failure etc. We should expect it to be incredibly rare that any given practice is appropriate across all those contexts, let alone that we could discover general best practices from the outcome of a few projects.

(See also [The generalizability crisis](https://osf.io/preprints/psyarxiv/jqw35_v1).)

## Details matter.

> Tacit knowledge or implicit knowledge - as opposed to formal, codified or explicit knowledge - is knowledge that is difficult to express or extract, and thus more difficult to transfer to others by means of writing it down or verbalizing it. This can include personal wisdom, experience, insight, and intuition.
>
> [...] the ability to speak a language, ride a bicycle, knead dough, play a musical instrument, or design and use complex equipment requires all sorts of knowledge which is not always known explicitly, even by expert practitioners, and which is difficult or impossible to explicitly transfer to other people.
>
> -- [Wikipedia](https://en.wikipedia.org/wiki/Tacit_knowledge)

Programming practices are mostly tacit knowledge. Tacit knowledge isn't easy to share. An expert will relate some simple-sounding rule of thumb, but then grilling them on specific cases will quickly uncover a huge collection of exceptions and caveats that vary depending on the specific details of the situation. These are generated from many many past experiences and don't generalize well outside of the context of that body of experience.

Trying to apply the rule of thumb without knowing all those details tends to result in failure. Phrases like "don't repeat yourself", "you aren't going to need it", "separation of concerns", "test-driven development" etc were originally produced from some body of valid experience, but then wildly over-generalized and over-applied without any of the original nuance.

The way to convey tacit knowledge, if at all, is via the body of experiences that generated the rule. For this reason I find much more value in specific experience reports or in watching people actually working, as opposed to writing about general principles.

## Confusing means and ends

The goal is always to write a program that solves the problem at hand and that can be maintained over its useful lifetime.

Advice like "write short functions" is a technique that may help achieve that goal in many situations, but it's not a goal in itself. And yet some characteristic of human thinking makes it very easy for these sort of pseudo-goals to take over from the actual goals. So you may hear people saying that some piece of software is bad *because* it has very long functions, even if the evidence suggests that it also happens to be easy to maintain.

When means and ends are confused, it's also often accompanied by the word "should" and other similar phrases that carry some moral or hygienic weight (eg "the right way to do it", "clean code" vs "code smells"). This strips away any consideration of the context or goals of a specific project.

"If you write shorter functions it's often easier to isolate specific behaviors in unit tests" is a concrete claim linking behavior and outcomes that you can test and evaluate in the context of a specific project.

"You should write short functions" means that you are a bad programmer if you write long functions. There is nowhere for the conversation to go from there.

## No gradient

Technology companies often make incredible profits by using simple technology to solve a business problem. This means that programmers at those companies can make a lot of bad decisions and adopt poor practices and still be successful. If money falls out of the sky whatever you do, there isn't much of a gradient to help discover better practices.

For example [slack](https://slack.com/) is an incredibly successful product. But it seems like every week I encounter a new bug that makes it completely unusable for me, from [taking seconds per character when typing](https://www.scattered-thoughts.net/writing/on-bad-advice/slack1.png) to [being completely unable to render messages](https://www.scattered-thoughts.net/writing/on-bad-advice/slack2.png). ([Discord](https://discord.com/) on the other hand has always been reliable and snappy despite, judging by my highly scientific googling, having 1/3rd as many employees. So it's not like chat apps are just intrinsically hard.) And yet slack's technical advice [is popular](https://hn.algolia.com/?dateRange=all&page=0&prefix=false&query=slack.engineering&sort=byPopularity&type=story) and if I ran across it without having experienced the results myself it would probably seem compelling.

## Wrong gradient

Social sites like reddit, hacker news, twitter etc are dominant in deciding a large portion of the reading material for myself and most other programmers I know. These sites strongly select for short, easy to read, entertaining and pseudo-controversial opinions. The tech community also skews heavily towards young and inexperienced because of it's rapid growth, so voting mechanisms aren't a useful mechanism for distinguishing boring good ideas from entertaining bad ideas.

I also suspect that the dynamics are sometimes self-reinforcing. After seeing many highly-voted comments endorsing some particular idea or motto, it starts to sound like it must be widely known to be true. So when you see new comments with the same idea you upvote them for giving the correct answer. This could allow ideas to persist without needing to be reinforced by any actual success. (See also [Applause lights](https://www.lesswrong.com/posts/dLbkrPu5STNCBLRjr/applause-lights).)

## What lasts

Looking back at the small subset of writing that has, in hindsight, turned out to help me get things done, it tends to be from people who:

- have multiple decades of experience
- have substantial technical achievements
- are measured and thoughtful rather than highly confident
- admit complexity and subtlety rather than having one method to rule them all

For example, on the subject of how to organize code into functions, contrast [Martin Fowler](https://martinfowler.com/bliki/FunctionLength.html):

> If you have to spend effort into looking at a fragment of code to figure out what it's doing, then you **should** extract it into a function and name the function after that 'what'.

> Any function more than half-a-dozen lines of code starts to smell to me [...]

Vs [John Carmack](http://number-none.com/blow/john_carmack_on_inlined_code.html):

> I'm not going to issue any mandates, but I want everyone to seriously consider some of these issues.
>
> If a function is only called from a single place, consider inlining it.
>
> If a function is called from multiple places, see if it is possible to arrange for the work to be done in a single place, perhaps with flags, and inline that.
>
> If there are multiple versions of a function, consider making a single function with more, possibly defaulted, parameters.
>
> If the work is close to purely functional, with few references to global state, try to make it completely functional.
>
> Try to use const on both parameters and functions when the function really must be used in multiple places.
>
> Minimize control flow complexity and "area under ifs", favoring consistent execution paths and times over "optimally" avoiding unnecessary work.
>
> To make things more complicated, the 'do always, then inhibit or ignore' strategy, while a very good idea for high reliability systems, is less appropriate in power and thermal constrained environments like mobile.

## On hopefully less bad advice

In the rest of this series I'm hoping to avoid, or at least temper, the failure modes above.

First, let me be explicit about the context that I'm writing from:

- ~70% self-employed and ~30% working at small early-stage companies.
- ~40% production code vs ~60% research code (ie no serious production usage, no long-term maintenance)
- ~30% in codebases with >100kloc vs ~70% small or green-field projects.
- Mostly systems problems, especially database engines and declarative languages.
- Some UI work, but all of it exploratory rather than production.
- I've never had to maintain a codebase for more than 2 years.
- I've never been responsible for running a long-lived service.

Any thing that I report having worked well for me has to be considered in that limited context.

Second, I'm aiming to accompany every idea with multiple examples. This helps convey the actual details and ensures I'm talking about things that I actually do, rather than things I think I should do.

Third, where I can I'm including counterexamples where something I used to think was a good idea caused problems or was applied poorly.
