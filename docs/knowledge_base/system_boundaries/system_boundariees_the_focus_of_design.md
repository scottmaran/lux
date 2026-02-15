---
title: "System boundaries: the focus of design"
source_url: https://www.tedinski.com/2018/02/06/system-boundaries.html
published: 2018-02-06T15:55:12-06:00
captured: 2026-02-15T12:01:11-05:00
tags: [boundaries]
---

# System boundaries: the focus of design

*Feb 6, 2018*

The best approach we have for doing software development is [iterative improvement](https://www.tedinski.com/2018/01/16/how-humans-write-programs.html). We have to start with something and then we can figure out how to make it better. Since we’re embracing an approach where some design fixes can be put off until later, what should we prioritize to fix sooner? The quick answer is: anything that’s difficult to change later. But what is that?

## What are system boundaries?

A system boundary is a publicly exposed interface that third-party developers are going to use. Maybe they’re truly external users: an open source library used by who knows who. Maybe they’re indirectly external: the API for a phone app you control, but you can’t make users upgrade to newer versions, so you can’t break the old API. Maybe they’re fictional: the users are internal, but you want to cut down on communication costs between teams, so you wall things off as if it’s a public release. Sometimes it’s unintentional: something so widely depended upon that the costs of changing it are too high, even if you actually control all the code involved.

It’s the inability to make breaking changes because you have (or are acting like you have) external users to support that really defines a boundary. As a result, you have to pay special attention to get the design of a system boundary right—it’s not easy to make changes in the future. Boundaries are more important than other parts of our programs that we can refactor at will.

A system boundary usually takes the form of a versioned artifact in some fashion. We know it’s inevitable that we’ll have to break things, so we try to only do that with new major versions. With a boundary, we have a responsibility to external users, and versioning puts the onus on us. We can decide if the benefits of a breaking change are large enough to merit having to also maintain another older version.

## Why do we create boundaries?

At first, it seems like boundaries are found things—that is, when there’s outside users of something, it becomes a boundary. But really it’s the other way around: we actively create boundaries, and that’s when outside users might start using them.

The original motivation for MVC is to permit re-use of the model with multiple views (and controllers). Thus, the model does not know about the view. This necessitated tricks like the “observer pattern” to allow a stateful model to notify views of updates without introducing the reverse dependency.

The primary reason we like boundaries is that they’re the only approach we have to truly re-using code. “Reusability” has been a grail of software design for longer than I’ve been paying attention. It might actually be slightly overrated (more on that someday) but when we’ve designed an abstraction well, the ability to re-use it is invaluable.

This is part of the reason we often simulate boundaries even internally to a program. If we write some piece of code, create some abstraction, and keep it in deliberate ignorance of (decoupling it from) its users, we can re-use it.

## Boundaries aren’t free

But while introducing boundaries has its re-use benefits, it also introduces costs. Changes cannot be easily made anymore. Multiple versions may need maintaining. Different dependencies may themselves depend on different versions of the same library, and this imposes costs on anyone who uses a library. If you want it to be used, you also need documentation explaining how to use it (even just to future-you, never forget about future-you.)

The early years of the Node/NPM ecosystem were flush with enthusiasm for a “micro-packages” concept. ([A blog post from 2013, for example.](http://blog.izs.me/post/48281998870/unix-philosophy-and-nodejs)) I think this enthusiasm has waned a bit, especially since the [`left-pad`](https://www.theregister.co.uk/2016/03/23/npm_left_pad_chaos/) fiasco. The idea had merits: besides re-use, I think the “approachability” of contributing patches to tiny open-source upstream projects was interesting. But I think the community seriously underestimated the costs involved in having a lot of (even just transitive) dependencies.

### Aside: Mono-repos

Incidentally, I suspect this is a major reason many companies opt for mono-repos for their software. If every internal library is an independent project, then you’re artificially creating system boundaries. Cross-project patches (changing an interface and all users of it) become more difficult to accomplish.

I think there’s a temptation to look down on this practice: “Oh, they must be botching their designs and not taking seriously the responsibilities of maintainership.” But why make things harder for ourselves? Why dilute our attention on more system boundaries that we need to? There are immense responsibilities for maintaining system boundaries, so we shouldn’t start piling them up where they’re not needed.

Further, mono-repos may simply be part of a different “contract” with users. Instead of supporting older versions (imposing a cost only on the library developer), you instead split the costs a little bit. Library developers have to write patches to downstream projects on any breaking change, and downstream projects have to review these patches in a timely manner. This isn’t a contract that works with external users, but with internal users where you can expect these responsibilities to be honored, it has its benefits.

## Controlling dependencies

A big part of software design is the design of the abstractions themselves, of course. But equally important at a high-level are dependencies. It’s not just that dependencies have costs, it’s also a major design element.

The single most important thing about any module is what modules it does not depend upon. It’s one of the most effective decoupling tools possible, to not even allow one module to reference another.

It’s also an immense help in understanding a module. The fewer dependencies it has, the more it can be understood on its own, independently of the rest of the system. It’s sometimes nice to write code in a way that deliberately cuts itself off from the rest of the system, just so it’s clear it’s independent.

## The rules are different at boundaries

There are a lot of opinions about software design out there, and a lot of disagreement about which are any good. But a significant problem with a lot of this discourse is that either people ignore context (and argue fruitlessly), or they chalk all disagreement up to some undefined nebulous “context” that explains everything. This is, of course, a useless explanation.

For example, DRY—don’t repeat yourself—is a common refrain among many programmers. And why not avoid duplication of similar looking code? So that makes sense.

But then we see a response from overzealous use in the wild: “boolean parameters on functions are a code smell!” These people see the logical end result of this: we have two similar things with a slight difference, so we refactor it into one function with a flag. But eventually someone finds functions with 3 boolean parameters, capable of working 8 different ways, actually only ever used 3 different ways. All this has done is create complexity. So it makes sense to push back, too.

But then which is right? The easiest answer here is “whatever.” It doesn’t matter. If you don’t like it, refactor it. The important thing here is only that you don’t end up with a poorly designed function with boolean parameters exposed on a system boundary. Because now you’re stuck with it. Internally, it’s a lot less important.

Whether we’re designing something on a system boundary, or not, is one of those things in that nebulous “context.”

## The takeaway

Were you ever taught to design a library? I don’t think I ever was. The closest class I can think of is compilers, to be honest. It’s the only course that had us build a big enough program that how to structure it was an important part of the class.

Most everything we learn about how to design libraries comes from three sources. First, we get direct experience making mistakes we regret. Second, we can get mentoring from someone who knows better than us. Third, we can try to learn from existing libraries. If you think someone else has written a good book on the topic, I’d like to hear about it.
